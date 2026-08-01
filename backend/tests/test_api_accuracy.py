from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.db import Base, get_engine, get_session_factory
from app.main import app, get_artifact_dir, get_db
from app.ml.backtest import BacktestResult


@pytest.fixture
def client_with_db(tmp_path):
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = get_session_factory(engine)()

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_artifact_dir] = lambda: tmp_path
    yield TestClient(app)
    app.dependency_overrides.clear()


@patch("app.routers.accuracy.load_latest_artifact")
@patch("app.routers.accuracy.run_backtest")
def test_get_accuracy_returns_backtest_metrics(mock_backtest, mock_load, client_with_db):
    mock_load.return_value = {"labels": ["H", "A"]}
    mock_backtest.return_value = BacktestResult(
        sport="nba", predictions_evaluated=120,
        model_accuracy=0.58, model_log_loss=0.65, model_brier_score=0.23,
        baseline_accuracy=0.53, baseline_log_loss=15.2, baseline_brier_score=0.47,
    )

    response = client_with_db.get("/accuracy?sport=nba")

    assert response.status_code == 200
    body = response.json()
    assert body["predictions_evaluated"] == 120
    assert body["model_accuracy"] == 0.58
    assert body["baseline_accuracy"] == 0.53


def test_get_accuracy_503_when_no_artifact(client_with_db):
    response = client_with_db.get("/accuracy?sport=nba")
    assert response.status_code == 503
