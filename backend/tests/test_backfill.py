from unittest.mock import patch

from app.db import Base, get_engine, get_session_factory
from app.ingestion.backfill import backfill_nba, backfill_soccer
from app.models_db import Match


def make_db():
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return get_session_factory(engine)()


@patch("app.ingestion.backfill.fetch_games")
def test_backfill_nba_paginates_until_no_next_cursor(mock_fetch):
    db = make_db()
    mock_fetch.side_effect = [
        {
            "data": [{
                "id": 1, "date": "2026-01-01T00:00:00.000Z",
                "home_team": {"id": 1, "full_name": "Lakers"},
                "visitor_team": {"id": 2, "full_name": "Celtics"},
                "home_team_score": 100, "visitor_team_score": 90, "status": "Final",
            }],
            "meta": {"next_cursor": 5},
        },
        {
            "data": [{
                "id": 2, "date": "2026-01-02T00:00:00.000Z",
                "home_team": {"id": 1, "full_name": "Lakers"},
                "visitor_team": {"id": 3, "full_name": "Nets"},
                "home_team_score": 95, "visitor_team_score": 99, "status": "Final",
            }],
            "meta": {"next_cursor": None},
        },
    ]

    count = backfill_nba(db, api_key="secret", seasons=["2025-2026"])

    assert count == 2
    assert db.query(Match).count() == 2
    assert mock_fetch.call_count == 2


@patch("app.ingestion.backfill.fetch_matches")
def test_backfill_soccer_pulls_each_league_and_season(mock_fetch):
    db = make_db()
    mock_fetch.side_effect = [
        {
            "matches": [{
                "id": 1, "utcDate": "2026-02-01T15:00:00Z",
                "homeTeam": {"id": 10, "name": "Arsenal"},
                "awayTeam": {"id": 20, "name": "Chelsea"},
                "score": {"fullTime": {"home": 2, "away": 1}},
                "status": "FINISHED",
            }]
        },
        {
            "matches": [{
                "id": 2, "utcDate": "2026-02-02T20:00:00Z",
                "homeTeam": {"id": 30, "name": "Real Madrid"},
                "awayTeam": {"id": 40, "name": "Barcelona"},
                "score": {"fullTime": {"home": 1, "away": 1}},
                "status": "FINISHED",
            }]
        },
    ]

    count = backfill_soccer(db, api_key="secret", leagues=["EPL", "La Liga"], seasons=[2024])

    assert count == 2
    assert mock_fetch.call_count == 2
    assert db.query(Match).count() == 2


@patch("app.ingestion.backfill.fetch_games")
def test_backfill_nba_skips_bad_game_and_keeps_going(mock_fetch):
    db = make_db()
    mock_fetch.return_value = {
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

    count = backfill_nba(db, api_key="secret", seasons=["2025-2026"])

    assert count == 1
    assert db.query(Match).count() == 1
