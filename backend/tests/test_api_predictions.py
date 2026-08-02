from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.db import Base, get_engine, get_session_factory
from app.main import app, get_artifact_dir, get_db
from app.ml.explain import Explanation, ExplanationFactor
from app.ml.predict import Prediction
from app.ml.simulate import ScorelineResult, SimulationResult
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
    mock_predict.return_value = Prediction(0.65, None, 0.35, 105.0, 99.0, "High")

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
    mock_predict.return_value = Prediction(0.65, None, 0.35, 105.0, 99.0, "High")

    response = client.get(f"/predictions/{match.id}")

    assert response.status_code == 200
    assert response.json()["game_id"] == match.id


def test_get_prediction_404_for_unknown_id(client_with_db):
    client, _ = client_with_db
    response = client.get("/predictions/999999")
    assert response.status_code == 404


@patch("app.routers.predictions.load_latest_artifact")
@patch("app.routers.predictions.explain_prediction")
def test_get_explanation_returns_factors_and_confidence(mock_explain, mock_load, client_with_db):
    client, match = client_with_db
    mock_load.return_value = {"labels": ["H", "A"]}
    mock_explain.return_value = Explanation(
        factors=[
            ExplanationFactor(name="home_form_last5", label="Home team's recent form", relative_influence_pct=42.0),
            ExplanationFactor(name="away_rest_days", label="Away team's rest advantage", relative_influence_pct=-8.0),
        ],
        model_confidence="High",
    )

    response = client.get(f"/predictions/{match.id}/explain")

    assert response.status_code == 200
    body = response.json()
    assert body["game_id"] == match.id
    assert body["model_confidence"] == "High"
    assert body["factors"][0]["name"] == "home_form_last5"
    assert body["factors"][0]["relative_influence_pct"] == 42.0


def test_get_explanation_404_for_unknown_id(client_with_db):
    client, _ = client_with_db
    response = client.get("/predictions/999999/explain")
    assert response.status_code == 404


def test_get_explanation_503_when_no_artifact(client_with_db):
    client, match = client_with_db
    response = client.get(f"/predictions/{match.id}/explain")
    assert response.status_code == 503


@patch("app.routers.predictions.load_latest_artifact")
@patch("app.routers.predictions.simulate_match")
def test_get_simulation_returns_scorelines_and_outcome_percentages(mock_simulate, mock_load, client_with_db):
    client, match = client_with_db
    mock_load.return_value = {"labels": ["H", "A"]}
    mock_simulate.return_value = SimulationResult(
        home_win_pct=62.5,
        draw_pct=None,
        away_win_pct=37.5,
        top_scorelines=[ScorelineResult(home_score=2, away_score=1, frequency_pct=8.4)],
        n_simulations=10000,
    )

    response = client.get(f"/predictions/{match.id}/simulate")

    assert response.status_code == 200
    body = response.json()
    assert body["game_id"] == match.id
    assert body["home_win_pct"] == 62.5
    assert body["n_simulations"] == 10000
    assert body["top_scorelines"][0]["home_score"] == 2


def test_get_simulation_404_for_unknown_id(client_with_db):
    client, _ = client_with_db
    response = client.get("/predictions/999999/simulate")
    assert response.status_code == 404


def test_get_simulation_503_when_no_artifact(client_with_db):
    client, match = client_with_db
    response = client.get(f"/predictions/{match.id}/simulate")
    assert response.status_code == 503


@patch("app.routers.predictions.load_latest_artifact")
@patch("app.routers.predictions.simulate_match")
def test_get_simulation_clamps_n_query_param(mock_simulate, mock_load, client_with_db):
    client, match = client_with_db
    mock_load.return_value = {"labels": ["H", "A"]}
    mock_simulate.return_value = SimulationResult(
        home_win_pct=50.0, draw_pct=None, away_win_pct=50.0, top_scorelines=[], n_simulations=50000,
    )

    client.get(f"/predictions/{match.id}/simulate?n=999999999")

    assert mock_simulate.call_args.kwargs["n_simulations"] == 50000


def test_get_match_context_returns_empty_lists_with_no_history(client_with_db):
    client, match = client_with_db
    response = client.get(f"/predictions/{match.id}/context")

    assert response.status_code == 200
    body = response.json()
    assert body["game_id"] == match.id
    assert body["home_recent_form"] == []
    assert body["away_recent_form"] == []
    assert body["head_to_head"] == []


def test_get_match_context_404_for_unknown_id(client_with_db):
    client, _ = client_with_db
    response = client.get("/predictions/999999/context")
    assert response.status_code == 404


def test_get_match_context_does_not_require_a_trained_model(client_with_db):
    # No dependency override / mock for load_latest_artifact here — this
    # endpoint must not need one at all, unlike /explain and /simulate.
    client, match = client_with_db
    response = client.get(f"/predictions/{match.id}/context")
    assert response.status_code == 200


@patch("app.routers.predictions.load_latest_artifact")
@patch("app.routers.predictions.simulate_counterfactual")
def test_get_whatif_returns_original_and_counterfactual(mock_counterfactual, mock_load, client_with_db):
    client, match = client_with_db
    mock_load.return_value = {"labels": ["H", "A"]}
    mock_counterfactual.return_value = (
        Prediction(0.6, None, 0.4, 100.0, 95.0, "Medium"),
        Prediction(0.9, None, 0.1, 108.0, 90.0, "High"),
    )

    response = client.get(f"/predictions/{match.id}/whatif?home_form_last5=0.95")

    assert response.status_code == 200
    body = response.json()
    assert body["overrides_applied"] == {"home_form_last5": 0.95}
    assert body["original"]["home_win_prob"] == 0.6
    assert body["counterfactual"]["home_win_prob"] == 0.9


def test_get_whatif_400_for_unknown_feature(client_with_db):
    client, match = client_with_db
    with patch("app.routers.predictions.load_latest_artifact", return_value={"labels": ["H", "A"]}):
        response = client.get(f"/predictions/{match.id}/whatif?opponent_missing_striker=1")
    assert response.status_code == 400


def test_get_whatif_400_for_non_numeric_value(client_with_db):
    client, match = client_with_db
    with patch("app.routers.predictions.load_latest_artifact", return_value={"labels": ["H", "A"]}):
        response = client.get(f"/predictions/{match.id}/whatif?home_form_last5=not-a-number")
    assert response.status_code == 400


def test_get_whatif_404_for_unknown_id(client_with_db):
    client, _ = client_with_db
    response = client.get("/predictions/999999/whatif")
    assert response.status_code == 404


@patch("app.routers.predictions.load_latest_artifact")
@patch("app.routers.predictions.predict_match")
def test_upcoming_mixes_leagues_instead_of_one_league_crowding_out_others(mock_predict, mock_load, tmp_path):
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = get_session_factory(engine)()

    home = Team(external_id="1", sport="football", league="La Liga", name="Alaves")
    away = Team(external_id="2", sport="football", league="La Liga", name="Getafe")
    db.add_all([home, away])
    db.commit()

    # La Liga's fixtures all fall earlier than the single Bundesliga fixture,
    # mirroring the real-world case where leagues start their seasons on
    # different dates.
    for i in range(15):
        db.add(Match(
            external_id=f"la-liga-{i}", sport="football", league="La Liga",
            date=datetime.utcnow() + timedelta(days=1, hours=i),
            home_team_id=home.id, away_team_id=away.id,
            home_score=None, away_score=None, status="scheduled",
        ))

    bundesliga_home = Team(external_id="3", sport="football", league="Bundesliga", name="Bayern")
    bundesliga_away = Team(external_id="4", sport="football", league="Bundesliga", name="Dortmund")
    db.add_all([bundesliga_home, bundesliga_away])
    db.commit()
    db.add(Match(
        external_id="bundesliga-1", sport="football", league="Bundesliga",
        date=datetime.utcnow() + timedelta(days=20),
        home_team_id=bundesliga_home.id, away_team_id=bundesliga_away.id,
        home_score=None, away_score=None, status="scheduled",
    ))
    db.commit()

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_artifact_dir] = lambda: tmp_path
    mock_load.return_value = {"labels": ["H", "D", "A"]}
    mock_predict.return_value = Prediction(0.5, 0.25, 0.25, 1.5, 1.0, "Medium")

    client = TestClient(app)
    response = client.get("/predictions/upcoming?sport=football")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    leagues_in_response = {item["league"] for item in response.json()}
    assert "Bundesliga" in leagues_in_response
    assert "La Liga" in leagues_in_response


@patch("app.routers.predictions.load_latest_artifact")
@patch("app.routers.predictions.predict_match")
def test_upcoming_filters_to_one_league_when_requested(mock_predict, mock_load, tmp_path):
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = get_session_factory(engine)()

    la_liga_home = Team(external_id="1", sport="football", league="La Liga", name="Alaves")
    la_liga_away = Team(external_id="2", sport="football", league="La Liga", name="Getafe")
    bundesliga_home = Team(external_id="3", sport="football", league="Bundesliga", name="Bayern")
    bundesliga_away = Team(external_id="4", sport="football", league="Bundesliga", name="Dortmund")
    db.add_all([la_liga_home, la_liga_away, bundesliga_home, bundesliga_away])
    db.commit()

    db.add(Match(
        external_id="la-liga-1", sport="football", league="La Liga",
        date=datetime.utcnow() + timedelta(days=1),
        home_team_id=la_liga_home.id, away_team_id=la_liga_away.id,
        home_score=None, away_score=None, status="scheduled",
    ))
    db.add(Match(
        external_id="bundesliga-1", sport="football", league="Bundesliga",
        date=datetime.utcnow() + timedelta(days=1),
        home_team_id=bundesliga_home.id, away_team_id=bundesliga_away.id,
        home_score=None, away_score=None, status="scheduled",
    ))
    db.commit()

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_artifact_dir] = lambda: tmp_path
    mock_load.return_value = {"labels": ["H", "D", "A"]}
    mock_predict.return_value = Prediction(0.5, 0.25, 0.25, 1.5, 1.0, "Medium")

    client = TestClient(app)
    response = client.get("/predictions/upcoming?sport=football&league=Bundesliga")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["league"] == "Bundesliga"
