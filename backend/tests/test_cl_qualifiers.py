from unittest.mock import patch

from app.db import Base, get_engine, get_session_factory
from app.ingestion.cl_qualifiers import sync_cl_qualifiers
from app.models_db import Match


def make_db():
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return get_session_factory(engine)()


def _fixture(fixture_id, round_name, status_short="NS"):
    return {
        "fixture": {"id": fixture_id, "date": "2026-08-11T19:00:00+00:00", "status": {"long": "", "short": status_short}},
        "league": {"id": 2, "name": "UEFA Champions League", "season": 2026, "round": round_name},
        "teams": {
            "home": {"id": 611, "name": "Sturm Graz"},
            "away": {"id": 645, "name": "Fenerbahce"},
        },
        "goals": {"home": None, "away": None},
    }


@patch("app.ingestion.cl_qualifiers.fetch_fixtures")
def test_sync_cl_qualifiers_only_ingests_qualifying_and_playoff_rounds(mock_fetch):
    db = make_db()
    mock_fetch.return_value = {
        "response": [
            _fixture(1, "1st Qualifying Round"),
            _fixture(2, "3rd Qualifying Round"),
            _fixture(3, "Play-offs"),
            _fixture(4, "Preliminary Round 3"),
            _fixture(5, "League Stage"),  # already covered by football-data.org, should be skipped
        ]
    }

    count = sync_cl_qualifiers(db, api_key="secret", season=2026)

    assert count == 4
    assert db.query(Match).count() == 4


@patch("app.ingestion.cl_qualifiers.fetch_fixtures")
def test_sync_cl_qualifiers_skips_bad_fixture_and_keeps_going(mock_fetch):
    db = make_db()
    bad_fixture = _fixture(1, "1st Qualifying Round")
    bad_fixture["fixture"]["date"] = "not-a-valid-date"
    mock_fetch.return_value = {
        "response": [
            bad_fixture,
            _fixture(2, "2nd Qualifying Round"),
        ]
    }

    count = sync_cl_qualifiers(db, api_key="secret", season=2026)

    assert count == 1
    assert db.query(Match).count() == 1
