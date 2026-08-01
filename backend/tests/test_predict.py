from pathlib import Path
from unittest.mock import MagicMock

import joblib
import numpy as np

from app.features.build_features import MatchFeatures
from app.ml.predict import load_latest_artifact, predict_match


def test_load_latest_artifact_returns_none_when_missing(tmp_path: Path):
    assert load_latest_artifact("nba", tmp_path) is None


def test_load_latest_artifact_loads_saved_file(tmp_path: Path):
    joblib.dump({"labels": ["H", "A"]}, tmp_path / "nba_latest.joblib")
    artifact = load_latest_artifact("nba", tmp_path)
    assert artifact["labels"] == ["H", "A"]


def test_predict_match_nba_returns_two_way_probs():
    classifier = MagicMock()
    classifier.predict_proba.return_value = np.array([[0.7, 0.3]])
    regressor_home = MagicMock()
    regressor_home.predict.return_value = np.array([105.0])
    regressor_away = MagicMock()
    regressor_away.predict.return_value = np.array([98.0])

    artifact = {
        "classifier": classifier,
        "regressor_home": regressor_home,
        "regressor_away": regressor_away,
        "feature_columns": ["home_form_last5", "away_form_last5", "home_win_rate_home", "away_win_rate_away", "h2h_home_win_rate", "home_rest_days", "away_rest_days"],
        "labels": ["H", "A"],
    }
    features = MatchFeatures(0.6, 0.4, 0.7, 0.5, 0.5, 2, 3)

    prediction = predict_match(artifact, features)

    assert prediction.home_win_prob == 0.7
    assert prediction.away_win_prob == 0.3
    assert prediction.draw_prob is None
    assert prediction.predicted_home_score == 105.0
    assert prediction.predicted_away_score == 98.0
    assert prediction.confidence == "High"  # top prob 0.7 >= 0.65 threshold for a 2-way outcome
