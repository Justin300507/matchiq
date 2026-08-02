from datetime import datetime, timedelta

from app.db import Base, get_engine, get_session_factory
from app.ml.match_context import compute_match_context
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
    match = Match(
        external_id=f"m-{home.id}-{away.id}-{day}",
        sport=sport, league=league,
        date=datetime(2025, 1, 1) + timedelta(days=day),
        home_team_id=home.id, away_team_id=away.id,
        home_score=home_score, away_score=away_score, status="final",
    )
    db.add(match)
    db.commit()
    return match


def test_compute_match_context_only_uses_matches_before_target_date():
    db = make_db()
    lakers = add_team(db, "1", "Lakers")
    celtics = add_team(db, "2", "Celtics")
    nets = add_team(db, "3", "Nets")

    add_match(db, lakers, nets, 0, 110, 90)  # Lakers win, before target
    target = add_match(db, lakers, celtics, 5, 100, 95)
    add_match(db, lakers, nets, 10, 90, 100)  # Lakers loss, AFTER target — must be excluded

    context = compute_match_context(db, target)

    assert len(context.home_recent_form) == 1
    assert context.home_recent_form[0].result == "W"
    assert context.home_recent_form[0].opponent_name == "Nets"


def test_compute_match_context_head_to_head_covers_both_venues():
    db = make_db()
    lakers = add_team(db, "1", "Lakers")
    celtics = add_team(db, "2", "Celtics")

    add_match(db, lakers, celtics, 0, 110, 100)  # Lakers win at home
    add_match(db, celtics, lakers, 3, 95, 90)    # Lakers loss away (Celtics win at home)
    target = add_match(db, lakers, celtics, 8, 100, 100)

    context = compute_match_context(db, target)

    assert len(context.head_to_head) == 2
    # Most recent first: the away loss, then the earlier home win.
    assert context.head_to_head[0].result == "L"
    assert context.head_to_head[1].result == "W"


def test_compute_match_context_limits_to_10_most_recent():
    db = make_db()
    lakers = add_team(db, "1", "Lakers")
    celtics = add_team(db, "2", "Celtics")

    for day in range(15):
        add_match(db, lakers, celtics, day, 100 + day, 90)
    target = add_match(db, lakers, celtics, 20, 100, 90)

    context = compute_match_context(db, target)

    assert len(context.home_recent_form) == 10
    assert len(context.away_recent_form) == 10
