from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.db import Base, get_engine, get_session_factory
from app.main import app, get_artifact_dir, get_db
from app.ml.predict import Prediction
from app.models_db import Match, Team


@pytest.fixture
def client_with_db(tmp_path):
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionFactory = get_session_factory(engine)
    db = SessionFactory()

    home = Team(external_id="1", sport="nba", league="NBA", name="Lakers")
    away = Team(external_id="2", sport="nba", league="NBA", name="Celtics")
    db.add_all([home, away])
    db.commit()

    match = Match(
        external_id="100", sport="nba", league="NBA",
        date=datetime.utcnow() + timedelta(days=1),
        home_team_id=home.id, away_team_id=away.id,
        home_score=None, away_score=None, status="scheduled",
    )
    db.add(match)
    db.commit()

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_artifact_dir] = lambda: tmp_path
    yield TestClient(app), match
    app.dependency_overrides.clear()


@patch("app.routers.predictions.load_latest_artifact")
@patch("app.routers.predictions.predict_match")
def test_upcoming_returns_predictions_for_sport(mock_predict, mock_load, client_with_db):
    client, match = client_with_db
    mock_load.return_value = {"labels": ["H", "A"]}
    mock_predict.return_value = Prediction(0.65, None, 0.35, 105.0, 99.0)

    response = client.get("/predictions/upcoming?sport=nba")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["home_team"]["name"] == "Lakers"
    assert body[0]["home_win_prob"] == 0.65


def test_upcoming_returns_503_when_no_artifact(client_with_db):
    client, _ = client_with_db
    response = client.get("/predictions/upcoming?sport=nba")
    assert response.status_code == 503


@patch("app.routers.predictions.load_latest_artifact")
@patch("app.routers.predictions.predict_match")
def test_get_prediction_by_id(mock_predict, mock_load, client_with_db):
    client, match = client_with_db
    mock_load.return_value = {"labels": ["H", "A"]}
    mock_predict.return_value = Prediction(0.65, None, 0.35, 105.0, 99.0)

    response = client.get(f"/predictions/{match.id}")

    assert response.status_code == 200
    assert response.json()["game_id"] == match.id


def test_get_prediction_404_for_unknown_id(client_with_db):
    client, _ = client_with_db
    response = client.get("/predictions/999999")
    assert response.status_code == 404
