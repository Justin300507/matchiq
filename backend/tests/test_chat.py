from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.db import Base, get_engine, get_session_factory
from app.main import app, get_artifact_dir, get_db


@pytest.fixture
def client_with_db(tmp_path):
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = get_session_factory(engine)()

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_artifact_dir] = lambda: tmp_path
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_chat_503_when_no_api_key_configured(client_with_db):
    with patch("app.routers.chat.get_settings", return_value=SimpleNamespace(anthropic_api_key="")):
        response = client_with_db.post("/chat", json={"sport": "nba", "question": "Any confident picks?"})

    assert response.status_code == 503


def test_chat_400_on_empty_question(client_with_db):
    with patch("app.routers.chat.get_settings", return_value=SimpleNamespace(anthropic_api_key="fake-key")):
        response = client_with_db.post("/chat", json={"sport": "nba", "question": "   "})

    assert response.status_code == 400


@patch("app.routers.chat.answer_question")
def test_chat_returns_answer_from_analyst(mock_answer, client_with_db):
    mock_answer.return_value = "The Lakers vs Celtics match has the highest home win probability."

    with patch("app.routers.chat.get_settings", return_value=SimpleNamespace(anthropic_api_key="fake-key")):
        response = client_with_db.post(
            "/chat", json={"sport": "nba", "league": None, "question": "Which match has the highest confidence?"}
        )

    assert response.status_code == 200
    body = response.json()
    assert "Lakers" in body["answer"]
    mock_answer.assert_called_once()
    args = mock_answer.call_args.args
    assert args[2] == "nba"
    assert args[4] == "Which match has the highest confidence?"
