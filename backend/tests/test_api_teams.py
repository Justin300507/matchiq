import pytest
from fastapi.testclient import TestClient

from app.db import Base, get_engine, get_session_factory
from app.main import app, get_db
from app.models_db import Team


@pytest.fixture
def client_with_db():
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = get_session_factory(engine)()
    team = Team(external_id="1", sport="nba", league="NBA", name="Lakers")
    db.add(team)
    db.commit()

    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app), team
    app.dependency_overrides.clear()


def test_get_team_by_id(client_with_db):
    client, team = client_with_db
    response = client.get(f"/teams/{team.id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Lakers"


def test_get_team_404_for_unknown_id(client_with_db):
    client, _ = client_with_db
    response = client.get("/teams/999999")
    assert response.status_code == 404


def test_get_team_profile_returns_stats_for_a_team_with_no_matches(client_with_db):
    client, team = client_with_db
    response = client.get(f"/teams/{team.id}/profile")

    assert response.status_code == 200
    body = response.json()
    assert body["team_id"] == team.id
    assert body["team_name"] == "Lakers"
    assert body["matches_played"] == 0
    assert body["elo_rating"] == 1500.0


def test_get_team_profile_404_for_unknown_id(client_with_db):
    client, _ = client_with_db
    response = client.get("/teams/999999/profile")
    assert response.status_code == 404
