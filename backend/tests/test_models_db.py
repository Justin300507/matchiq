from datetime import datetime

from app.db import Base, get_engine, get_session_factory
from app.models_db import Match, Team


def test_can_insert_team_and_match():
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = get_session_factory(engine)
    db = Session()

    home = Team(external_id="1", sport="nba", league="NBA", name="Lakers")
    away = Team(external_id="2", sport="nba", league="NBA", name="Celtics")
    db.add_all([home, away])
    db.commit()

    match = Match(
        external_id="100",
        sport="nba",
        league="NBA",
        date=datetime(2026, 1, 1),
        home_team_id=home.id,
        away_team_id=away.id,
        home_score=None,
        away_score=None,
        status="scheduled",
    )
    db.add(match)
    db.commit()

    fetched = db.query(Match).one()
    assert fetched.home_team.name == "Lakers"
    assert fetched.away_team.name == "Celtics"
    assert fetched.status == "scheduled"
