import random
from dataclasses import asdict
from datetime import datetime, timedelta

from sqlalchemy import event

from app.db import Base, get_engine, get_session_factory
from app.features.build_features import build_training_dataframe, compute_features, compute_features_bulk
from app.models_db import Match, Team


def make_db_with_synthetic_matches(n_teams=8, n_matches=120):
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = get_session_factory(engine)()

    random.seed(11)
    teams = [Team(external_id=str(i), sport="nba", league="NBA", name=f"Team{i}") for i in range(n_teams)]
    db.add_all(teams)
    db.commit()

    for day in range(n_matches):
        home, away = random.sample(teams, 2)
        db.add(Match(
            external_id=f"m{day}", sport="nba", league="NBA",
            date=datetime(2025, 1, 1) + timedelta(days=day),
            home_team_id=home.id, away_team_id=away.id,
            home_score=random.randint(90, 120), away_score=random.randint(90, 120), status="final",
        ))
    db.commit()
    return db, engine


def _count_queries(engine, fn):
    count = 0

    def _on_execute(*_args, **_kwargs):
        nonlocal count
        count += 1

    event.listen(engine, "before_cursor_execute", _on_execute)
    try:
        result = fn()
    finally:
        event.remove(engine, "before_cursor_execute", _on_execute)
    return result, count


def test_build_training_dataframe_matches_per_row_compute_features():
    db, _engine = make_db_with_synthetic_matches()

    bulk_df = build_training_dataframe(db, "nba")

    matches = (
        db.query(Match).filter(Match.sport == "nba", Match.status == "final").order_by(Match.date.asc()).all()
    )
    per_row_features = [asdict(compute_features(db, m)) for m in matches]

    for i, expected in enumerate(per_row_features):
        row = bulk_df.iloc[i]
        for key, value in expected.items():
            assert row[key] == value, f"row {i} field {key}: bulk={row[key]!r} per-row={value!r}"


def test_build_training_dataframe_issues_a_bounded_number_of_queries():
    db, engine = make_db_with_synthetic_matches(n_matches=120)

    df, query_count = _count_queries(engine, lambda: build_training_dataframe(db, "nba"))

    assert len(df) == 120
    # The old per-row approach issued ~5 queries per match (600+ for 120
    # matches). The bulk path issues exactly one query for the match list;
    # a generous ceiling here still proves the N+1 pattern is gone.
    assert query_count <= 5, f"expected O(1) queries, got {query_count}"


def _add_upcoming_matches(db, teams, n_upcoming=20, start_day=200):
    upcoming = []
    for i in range(n_upcoming):
        home, away = random.sample(teams, 2)
        match = Match(
            external_id=f"upcoming{i}", sport="nba", league="NBA",
            date=datetime(2025, 1, 1) + timedelta(days=start_day + i),
            home_team_id=home.id, away_team_id=away.id,
            home_score=None, away_score=None, status="scheduled",
        )
        db.add(match)
        upcoming.append(match)
    db.commit()
    return upcoming


def test_compute_features_bulk_matches_compute_features_for_upcoming_matches():
    db, _engine = make_db_with_synthetic_matches(n_matches=150)
    teams = db.query(Team).all()
    upcoming = _add_upcoming_matches(db, teams)

    bulk_features = compute_features_bulk(db, "nba", upcoming)

    for match in upcoming:
        assert bulk_features[match.id] == compute_features(db, match)


def test_compute_features_bulk_issues_a_bounded_number_of_queries():
    db, engine = make_db_with_synthetic_matches(n_matches=150)
    teams = db.query(Team).all()
    _add_upcoming_matches(db, teams, n_upcoming=30)

    # Re-fetch fresh, unexpired objects right before the counted call --
    # this mirrors the real endpoint, which queries the upcoming matches and
    # immediately computes their features in the same request with no commit
    # in between (a commit expires ORM objects, forcing a reload per
    # attribute access on next use -- an artifact of re-using objects across
    # a commit boundary in this test, not something the real request path
    # does).
    upcoming = db.query(Match).filter(Match.sport == "nba", Match.status == "scheduled").all()

    features, query_count = _count_queries(engine, lambda: compute_features_bulk(db, "nba", upcoming))

    assert len(features) == 30
    # The per-match approach would issue ~5 queries per upcoming match
    # (150+ for 30 matches, on top of whatever loaded the match list itself).
    assert query_count <= 5, f"expected O(1) queries, got {query_count}"


def test_compute_features_bulk_returns_empty_dict_for_no_targets():
    db, _engine = make_db_with_synthetic_matches()
    assert compute_features_bulk(db, "nba", []) == {}
