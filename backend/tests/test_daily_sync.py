from unittest.mock import patch

from app.db import Base, get_engine, get_session_factory
from app.ingestion.daily_sync import sync_recent
from app.models_db import Match


def make_db():
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return get_session_factory(engine)()


@patch("app.ingestion.daily_sync.fetch_matches")
@patch("app.ingestion.daily_sync.fetch_games")
def test_sync_recent_pulls_nba_and_all_soccer_leagues(mock_nba, mock_soccer):
    db = make_db()
    mock_nba.return_value = {"data": [], "meta": {"next_cursor": None}}
    mock_soccer.return_value = {"matches": []}

    sync_recent(db, nba_api_key="a", football_api_key="b")

    assert mock_nba.call_count == 1
    assert mock_soccer.call_count == 5  # one call per top-5 league


@patch("app.ingestion.daily_sync.fetch_matches")
@patch("app.ingestion.daily_sync.fetch_games")
def test_sync_recent_upserts_returned_games(mock_nba, mock_soccer):
    db = make_db()
    mock_nba.return_value = {
        "data": [{
            "id": 1, "date": "2026-01-01T00:00:00.000Z",
            "home_team": {"id": 1, "full_name": "Lakers"},
            "visitor_team": {"id": 2, "full_name": "Celtics"},
            "home_team_score": 100, "visitor_team_score": 90, "status": "Final",
        }],
        "meta": {"next_cursor": None},
    }
    mock_soccer.return_value = {"matches": []}

    count = sync_recent(db, nba_api_key="a", football_api_key="b")

    assert count == 1
    assert db.query(Match).count() == 1


@patch("app.ingestion.daily_sync.fetch_matches")
@patch("app.ingestion.daily_sync.fetch_games")
def test_sync_recent_skips_bad_game_and_keeps_going(mock_nba, mock_soccer):
    db = make_db()
    mock_nba.return_value = {
        "data": [
            {"id": 1, "date": "not-a-valid-date", "home_team": {"id": 1, "full_name": "Lakers"},
             "visitor_team": {"id": 2, "full_name": "Celtics"}, "home_team_score": 100,
             "visitor_team_score": 90, "status": "Final"},
            {"id": 2, "date": "2026-01-02T00:00:00.000Z", "home_team": {"id": 1, "full_name": "Lakers"},
             "visitor_team": {"id": 3, "full_name": "Nets"}, "home_team_score": 95,
             "visitor_team_score": 99, "status": "Final"},
        ],
        "meta": {"next_cursor": None},
    }
    mock_soccer.return_value = {"matches": []}

    count = sync_recent(db, nba_api_key="a", football_api_key="b")

    assert count == 1
    assert db.query(Match).count() == 1
