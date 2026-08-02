from datetime import datetime, timedelta

from app.copilot.lookups import find_team_by_name, find_upcoming_match
from app.db import Base, get_engine, get_session_factory
from app.models_db import Match, Team


def _make_db():
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return get_session_factory(engine)()


def test_find_team_by_name_matches_a_known_team():
    db = _make_db()
    db.add(Team(external_id="1", sport="nba", league="NBA", name="Los Angeles Lakers"))
    db.commit()

    team = find_team_by_name(db, "Lakers", "nba")

    assert team is not None
    assert team.name == "Los Angeles Lakers"


def test_find_team_by_name_returns_none_when_no_team_matches():
    db = _make_db()
    db.add(Team(external_id="1", sport="nba", league="NBA", name="Los Angeles Lakers"))
    db.commit()

    assert find_team_by_name(db, "Celtics", "nba") is None


def test_find_team_by_name_is_scoped_to_sport():
    db = _make_db()
    db.add(Team(external_id="1", sport="football", league="EPL", name="Arsenal"))
    db.commit()

    assert find_team_by_name(db, "Arsenal", "nba") is None


def _add_upcoming_match(db, home_name="Lakers", away_name="Celtics", sport="nba"):
    home = Team(external_id="h", sport=sport, league="NBA", name=home_name)
    away = Team(external_id="a", sport=sport, league="NBA", name=away_name)
    db.add_all([home, away])
    db.commit()
    match = Match(
        external_id="m1", sport=sport, league="NBA",
        date=datetime.utcnow() + timedelta(days=1),
        home_team_id=home.id, away_team_id=away.id,
        home_score=None, away_score=None, status="scheduled",
    )
    db.add(match)
    db.commit()
    return match


def test_find_upcoming_match_matches_regardless_of_home_away_order():
    db = _make_db()
    _add_upcoming_match(db)

    match = find_upcoming_match(db, "Celtics", "Lakers", "nba")

    assert match is not None
    assert match.home_team.name == "Lakers"


def test_find_upcoming_match_returns_none_when_no_match_found():
    db = _make_db()
    _add_upcoming_match(db)

    assert find_upcoming_match(db, "Warriors", "Nets", "nba") is None
