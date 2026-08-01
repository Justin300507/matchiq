from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from app.db import Base, get_engine, get_session_factory
from app.ml.analyst import answer_question
from app.ml.predict import Prediction
from app.models_db import Match, Team


def make_db_with_upcoming_match():
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = get_session_factory(engine)()

    home = Team(external_id="1", sport="nba", league="NBA", name="Lakers")
    away = Team(external_id="2", sport="nba", league="NBA", name="Celtics")
    db.add_all([home, away])
    db.commit()

    db.add(Match(
        external_id="m1", sport="nba", league="NBA",
        date=datetime.utcnow() + timedelta(days=1),
        home_team_id=home.id, away_team_id=away.id,
        home_score=None, away_score=None, status="scheduled",
    ))
    db.commit()
    return db


@patch("app.ml.analyst.anthropic.Anthropic")
@patch("app.ml.analyst.predict_match")
@patch("app.ml.analyst.load_latest_artifact")
def test_answer_question_includes_match_context_and_returns_text(mock_load, mock_predict, mock_anthropic_cls):
    db = make_db_with_upcoming_match()
    mock_load.return_value = {"labels": ["H", "A"]}
    mock_predict.return_value = Prediction(
        home_win_prob=0.7, draw_prob=None, away_win_prob=0.3,
        predicted_home_score=110.0, predicted_away_score=100.0, confidence="High",
    )

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_text_block = MagicMock(type="text", text="Lakers vs Celtics has the highest home win probability.")
    mock_response.content = [mock_text_block]
    mock_client.messages.create.return_value = mock_response
    mock_anthropic_cls.return_value = mock_client

    answer = answer_question(db, "/tmp/artifacts", "nba", None, "Which match is most confident?", "fake-key")

    assert answer == "Lakers vs Celtics has the highest home win probability."
    mock_anthropic_cls.assert_called_once_with(api_key="fake-key")

    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-opus-5"
    user_content = call_kwargs["messages"][0]["content"]
    assert "Lakers vs Celtics" in user_content
    assert "home_win_prob=0.70" in user_content
    assert "Which match is most confident?" in user_content


@patch("app.ml.analyst.load_latest_artifact")
def test_build_context_reports_when_no_model_available(mock_load):
    db = make_db_with_upcoming_match()
    mock_load.return_value = None

    from app.ml.analyst import _build_match_context

    context = _build_match_context(db, "/tmp/artifacts", "nba", None)
    assert "No trained prediction model" in context
