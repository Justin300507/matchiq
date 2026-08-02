from datetime import datetime, timedelta
from unittest.mock import patch

from app.copilot.tools import (
    get_market_odds,
    get_match_explanation,
    get_team_profile,
    get_upcoming_predictions,
)
from app.db import Base, get_engine, get_session_factory
from app.integrations.polymarket_odds import MarketOdds
from app.ml.explain import Explanation, ExplanationFactor
from app.ml.predict import Prediction
from app.models_db import Match, Team


def _make_db():
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return get_session_factory(engine)()


def _add_upcoming_match(db, home_name="Lakers", away_name="Celtics", sport="nba"):
    home = Team(external_id="h", sport=sport, league="NBA", name=home_name)
    away = Team(external_id="a", sport=sport, league="NBA", name=away_name)
    db.add_all([home, away])
    db.commit()
    match = Match(
        external_id="m1", sport=sport, league="NBA",
        date=datetime.utcnow() + timedelta(days=1),
        home_team_id=home.id, away_team_id=away.id,
        home_score=None, away_score=None, status="scheduled",
    )
    db.add(match)
    db.commit()
    return match


@patch("app.copilot.tools.predict_batch")
@patch("app.copilot.tools.load_latest_artifact")
def test_get_upcoming_predictions_lists_real_matches(mock_load, mock_predict):
    db = _make_db()
    _add_upcoming_match(db)
    mock_load.return_value = {"labels": ["H", "A"]}
    mock_predict.return_value = [Prediction(0.65, None, 0.35, 105.0, 99.0, "High")]

    result = get_upcoming_predictions(db, "/tmp/artifacts", sport="nba")

    assert "Lakers vs Celtics" in result
    assert "home_win_prob=0.65" in result


@patch("app.copilot.tools.load_latest_artifact")
def test_get_upcoming_predictions_reports_no_model(mock_load):
    db = _make_db()
    mock_load.return_value = None

    result = get_upcoming_predictions(db, "/tmp/artifacts", sport="nba")

    assert "No trained prediction model" in result


@patch("app.copilot.tools.load_latest_artifact")
def test_get_upcoming_predictions_reports_no_matches(mock_load):
    db = _make_db()
    mock_load.return_value = {"labels": ["H", "A"]}

    result = get_upcoming_predictions(db, "/tmp/artifacts", sport="nba")

    assert "no upcoming matches" in result.lower()


def test_get_team_profile_returns_real_stats():
    db = _make_db()
    db.add(Team(external_id="1", sport="nba", league="NBA", name="Los Angeles Lakers"))
    db.commit()

    result = get_team_profile(db, "/tmp/artifacts", team_name="Lakers", sport="nba")

    assert "Los Angeles Lakers" in result
    assert "Elo rating" in result


def test_get_team_profile_reports_team_not_found():
    db = _make_db()

    result = get_team_profile(db, "/tmp/artifacts", team_name="Nonexistent Team", sport="nba")

    assert "No team found" in result


@patch("app.copilot.tools.explain_prediction")
@patch("app.copilot.tools.predict_match")
@patch("app.copilot.tools.load_latest_artifact")
def test_get_match_explanation_returns_factors(mock_load, mock_predict, mock_explain):
    db = _make_db()
    _add_upcoming_match(db)
    mock_load.return_value = {"labels": ["H", "A"]}
    mock_predict.return_value = Prediction(0.65, None, 0.35, 105.0, 99.0, "High")
    mock_explain.return_value = Explanation(
        factors=[ExplanationFactor(
            name="home_form_last5", label="Home team's recent form", relative_influence_pct=42.0,
        )],
        model_confidence="High",
    )

    result = get_match_explanation(db, "/tmp/artifacts", home_team="Lakers", away_team="Celtics", sport="nba")

    assert "Lakers vs Celtics" in result
    assert "Home team's recent form" in result
    assert "42.0" in result


def test_get_match_explanation_reports_match_not_found():
    db = _make_db()

    result = get_match_explanation(db, "/tmp/artifacts", home_team="Lakers", away_team="Celtics", sport="nba")

    assert "No upcoming match found" in result


@patch("app.copilot.tools.find_match_odds")
def test_get_market_odds_returns_real_odds(mock_find):
    db = _make_db()
    _add_upcoming_match(db)
    mock_find.return_value = MarketOdds(
        source="Polymarket", event_title="Lakers vs. Celtics",
        event_url="https://polymarket.com/event/lakers-vs-celtics",
        home_decimal_odds=2.5, draw_decimal_odds=None, away_decimal_odds=1.8,
    )

    result = get_market_odds(db, "/tmp/artifacts", home_team="Lakers", away_team="Celtics", sport="nba")

    assert "2.5" in result
    assert "polymarket.com" in result


@patch("app.copilot.tools.find_match_odds")
def test_get_market_odds_reports_no_market(mock_find):
    db = _make_db()
    _add_upcoming_match(db)
    mock_find.return_value = None

    result = get_market_odds(db, "/tmp/artifacts", home_team="Lakers", away_team="Celtics", sport="nba")

    assert "No live Polymarket market" in result


def test_get_market_odds_reports_match_not_found():
    db = _make_db()

    result = get_market_odds(db, "/tmp/artifacts", home_team="Lakers", away_team="Celtics", sport="nba")

    assert "No upcoming match found" in result
