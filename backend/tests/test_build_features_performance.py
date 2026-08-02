import random
from dataclasses import asdict
from datetime import datetime, timedelta

from sqlalchemy import event

from app.db import Base, get_engine, get_session_factory
from app.features.build_features import build_training_dataframe, compute_features
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
