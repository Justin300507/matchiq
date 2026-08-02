from datetime import datetime, timedelta

from app.db import Base, get_engine, get_session_factory
from app.features.build_features import build_training_dataframe, compute_features
from app.models_db import Match, Team


def make_db():
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return get_session_factory(engine)()


def add_team(db, external_id, name, sport="nba", league="NBA"):
    team = Team(external_id=external_id, sport=sport, league=league, name=name)
    db.add(team)
    db.flush()
    return team


def add_match(db, home, away, day_offset, home_score, away_score, sport="nba", league="NBA", status="final"):
    match = Match(
        external_id=f"m{day_offset}-{home.id}-{away.id}",
        sport=sport,
        league=league,
        date=datetime(2026, 1, 1) + timedelta(days=day_offset),
        home_team_id=home.id,
        away_team_id=away.id,
        home_score=home_score,
        away_score=away_score,
        status=status,
    )
    db.add(match)
    db.commit()
    return match


def test_compute_features_uses_only_past_matches():
    db = make_db()
    lakers = add_team(db, "1", "Lakers")
    celtics = add_team(db, "2", "Celtics")
    nets = add_team(db, "3", "Nets")

    add_match(db, lakers, nets, day_offset=0, home_score=100, away_score=90)  # Lakers win, home
    add_match(db, celtics, lakers, day_offset=2, home_score=80, away_score=95)  # Lakers win, away

    target = add_match(db, lakers, celtics, day_offset=5, home_score=None, away_score=None)

    features = compute_features(db, target)

    assert features.home_form_last5 == 1.0  # Lakers won both prior games
    assert features.home_rest_days == 3  # last Lakers game was day 2, target is day 5


def test_build_training_dataframe_only_includes_final_matches():
    db = make_db()
    lakers = add_team(db, "1", "Lakers")
    celtics = add_team(db, "2", "Celtics")

    add_match(db, lakers, celtics, day_offset=0, home_score=100, away_score=90)
    add_match(db, lakers, celtics, day_offset=5, home_score=None, away_score=None, status="scheduled")  # scheduled, excluded

    df = build_training_dataframe(db, sport="nba")

    assert len(df) == 1
    assert df.iloc[0]["result"] == "H"
