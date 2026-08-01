from datetime import datetime, timedelta

from app.db import Base, get_engine, get_session_factory
from app.ml.elo import DEFAULT_RATING, compute_elo_ratings
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


def add_match(db, home, away, day, home_score, away_score, sport="nba", league="NBA"):
    db.add(Match(
        external_id=f"m-{home.id}-{away.id}-{day}",
        sport=sport, league=league,
        date=datetime(2025, 1, 1) + timedelta(days=day),
        home_team_id=home.id, away_team_id=away.id,
        home_score=home_score, away_score=away_score, status="final",
    ))
    db.commit()


def test_team_that_keeps_winning_rises_above_default_rating():
    db = make_db()
    strong = add_team(db, "1", "Strong")
    weak = add_team(db, "2", "Weak")
    for day in range(10):
        add_match(db, strong, weak, day, home_score=110, away_score=90)

    ratings = compute_elo_ratings(db, "nba")

    assert ratings[strong.id] > DEFAULT_RATING
    assert ratings[weak.id] < DEFAULT_RATING


def test_single_match_rating_change_is_zero_sum():
    db = make_db()
    home = add_team(db, "1", "Home")
    away = add_team(db, "2", "Away")
    add_match(db, home, away, 0, home_score=100, away_score=90)

    ratings = compute_elo_ratings(db, "nba")

    home_delta = ratings[home.id] - DEFAULT_RATING
    away_delta = ratings[away.id] - DEFAULT_RATING
    assert abs(home_delta + away_delta) < 1e-9


def test_team_with_no_matches_is_absent_from_ratings():
    db = make_db()
    home = add_team(db, "1", "Home")
    away = add_team(db, "2", "Away")
    bench = add_team(db, "3", "Bench")
    add_match(db, home, away, 0, home_score=100, away_score=90)

    ratings = compute_elo_ratings(db, "nba")

    assert bench.id not in ratings
