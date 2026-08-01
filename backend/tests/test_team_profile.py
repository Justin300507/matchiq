from datetime import datetime, timedelta

from app.db import Base, get_engine, get_session_factory
from app.ml.team_profile import compute_team_profile
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


def test_compute_team_profile_basic_record_and_goal_averages():
    db = make_db()
    lakers = add_team(db, "1", "Lakers")
    celtics = add_team(db, "2", "Celtics")

    add_match(db, lakers, celtics, 0, home_score=110, away_score=100)  # Lakers win (home)
    add_match(db, celtics, lakers, 1, home_score=95, away_score=105)  # Lakers win (away)
    add_match(db, lakers, celtics, 2, home_score=90, away_score=100)  # Lakers loss (home)

    profile = compute_team_profile(db, lakers)

    assert profile.matches_played == 3
    assert profile.wins == 2
    assert profile.losses == 1
    assert profile.draws == 0
    assert profile.goals_for_avg == (110 + 105 + 90) / 3
    assert profile.goals_against_avg == (100 + 95 + 100) / 3


def test_compute_team_profile_home_and_away_win_rate_split():
    db = make_db()
    lakers = add_team(db, "1", "Lakers")
    celtics = add_team(db, "2", "Celtics")

    add_match(db, lakers, celtics, 0, home_score=110, away_score=100)  # home win
    add_match(db, lakers, celtics, 1, home_score=90, away_score=100)  # home loss
    add_match(db, celtics, lakers, 2, home_score=95, away_score=105)  # away win

    profile = compute_team_profile(db, lakers)

    assert profile.home_win_rate == 0.5
    assert profile.away_win_rate == 1.0


def test_compute_team_profile_last5_form_is_chronological_oldest_to_newest():
    db = make_db()
    lakers = add_team(db, "1", "Lakers")
    celtics = add_team(db, "2", "Celtics")

    results = [
        (110, 100),  # W
        (90, 100),   # L
        (100, 100),  # D
        (120, 100),  # W
        (80, 100),   # L
        (130, 100),  # W (most recent)
    ]
    for day, (h, a) in enumerate(results):
        add_match(db, lakers, celtics, day, home_score=h, away_score=a)

    profile = compute_team_profile(db, lakers)

    # Only the most recent 5, oldest-to-newest: L, D, W, L, W
    assert profile.last5_form == "LDWLW"


def test_compute_team_profile_with_no_matches_does_not_crash():
    db = make_db()
    lonely = add_team(db, "1", "Lonely FC")

    profile = compute_team_profile(db, lonely)

    assert profile.matches_played == 0
    assert profile.goals_for_avg == 0.0
    assert profile.home_win_rate == 0.0
    assert profile.last5_form == ""
