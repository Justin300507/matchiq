from datetime import datetime

from app.db import Base, get_engine, get_session_factory
from app.ingestion.normalize import normalize_nba_game, normalize_soccer_game, upsert_game
from app.models_db import Match, Team


def make_db():
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return get_session_factory(engine)()


def test_normalize_nba_game_maps_fields():
    raw = {
        "id": 555,
        "date": "2026-01-15T00:00:00.000Z",
        "home_team": {"id": 1, "full_name": "Los Angeles Lakers"},
        "visitor_team": {"id": 2, "full_name": "Boston Celtics"},
        "home_team_score": 110,
        "visitor_team_score": 102,
        "status": "Final",
    }
    game = normalize_nba_game(raw)
    assert game.external_id == "555"
    assert game.sport == "nba"
    assert game.league == "NBA"
    assert game.home_team_name == "Los Angeles Lakers"
    assert game.away_team_name == "Boston Celtics"
    assert game.home_score == 110
    assert game.away_score == 102
    assert game.status == "final"


def test_normalize_soccer_game_maps_fields():
    raw = {
        "id": 777,
        "utcDate": "2026-02-01T15:00:00Z",
        "homeTeam": {"id": 10, "name": "Arsenal"},
        "awayTeam": {"id": 20, "name": "Chelsea"},
        "score": {"fullTime": {"home": 2, "away": 1}},
        "status": "FINISHED",
    }
    game = normalize_soccer_game(raw, league="EPL")
    assert game.external_id == "777"
    assert game.sport == "soccer"
    assert game.league == "EPL"
    assert game.home_team_name == "Arsenal"
    assert game.away_team_name == "Chelsea"
    assert game.home_score == 2
    assert game.away_score == 1
    assert game.status == "final"


def test_upsert_game_creates_teams_and_match():
    db = make_db()
    game = normalize_nba_game({
        "id": 555,
        "date": "2026-01-15T00:00:00.000Z",
        "home_team": {"id": 1, "full_name": "Los Angeles Lakers"},
        "visitor_team": {"id": 2, "full_name": "Boston Celtics"},
        "home_team_score": 110,
        "visitor_team_score": 102,
        "status": "Final",
    })

    match = upsert_game(db, game)

    assert db.query(Team).count() == 2
    assert db.query(Match).count() == 1
    assert match.home_score == 110


def test_upsert_game_is_idempotent():
    db = make_db()
    game = normalize_nba_game({
        "id": 555,
        "date": "2026-01-15T00:00:00.000Z",
        "home_team": {"id": 1, "full_name": "Los Angeles Lakers"},
        "visitor_team": {"id": 2, "full_name": "Boston Celtics"},
        "home_team_score": None,
        "visitor_team_score": None,
        "status": "Scheduled",
    })
    upsert_game(db, game)

    finished = normalize_nba_game({
        "id": 555,
        "date": "2026-01-15T00:00:00.000Z",
        "home_team": {"id": 1, "full_name": "Los Angeles Lakers"},
        "visitor_team": {"id": 2, "full_name": "Boston Celtics"},
        "home_team_score": 110,
        "visitor_team_score": 102,
        "status": "Final",
    })
    upsert_game(db, finished)

    assert db.query(Match).count() == 1
    assert db.query(Team).count() == 2
    assert db.query(Match).one().home_score == 110
