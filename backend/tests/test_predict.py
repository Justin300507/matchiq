from pathlib import Path
from unittest.mock import MagicMock

import joblib
import numpy as np

from app.features.build_features import MatchFeatures
from app.ml.predict import load_latest_artifact, predict_batch, predict_match


def test_load_latest_artifact_returns_none_when_missing(tmp_path: Path):
    assert load_latest_artifact("nba", tmp_path) is None


def test_load_latest_artifact_loads_saved_file(tmp_path: Path):
    joblib.dump({"labels": ["H", "A"]}, tmp_path / "nba_latest.joblib")
    artifact = load_latest_artifact("nba", tmp_path)
    assert artifact["labels"] == ["H", "A"]


def test_load_latest_artifact_caches_by_path_and_mtime(tmp_path: Path):
    joblib.dump({"labels": ["H", "A"]}, tmp_path / "nba_latest.joblib")

    first = load_latest_artifact("nba", tmp_path)
    second = load_latest_artifact("nba", tmp_path)

    assert first is second  # same object -- the file wasn't re-read from disk


def test_load_latest_artifact_reloads_after_the_file_changes(tmp_path: Path):
    path = tmp_path / "nba_latest.joblib"
    joblib.dump({"labels": ["H", "A"]}, path)
    first = load_latest_artifact("nba", tmp_path)

    # Force a distinct mtime (some filesystems have 1-2s mtime resolution)
    # so this reliably looks like a newer file, the way a real retrain would.
    joblib.dump({"labels": ["H", "D", "A"]}, path)
    import os
    import time
    os.utime(path, (time.time() + 5, time.time() + 5))

    second = load_latest_artifact("nba", tmp_path)

    assert second is not first
    assert second["labels"] == ["H", "D", "A"]


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


def test_predict_batch_matches_predict_match_for_each_row():
    classifier = MagicMock()
    classifier.predict_proba.return_value = np.array([[0.7, 0.3], [0.4, 0.6]])
    regressor_home = MagicMock()
    regressor_home.predict.return_value = np.array([105.0, 90.0])
    regressor_away = MagicMock()
    regressor_away.predict.return_value = np.array([98.0, 100.0])

    artifact = {
        "classifier": classifier,
        "regressor_home": regressor_home,
        "regressor_away": regressor_away,
        "feature_columns": ["home_form_last5", "away_form_last5", "home_win_rate_home", "away_win_rate_away", "h2h_home_win_rate", "home_rest_days", "away_rest_days"],
        "labels": ["H", "A"],
    }
    features_list = [MatchFeatures(0.6, 0.4, 0.7, 0.5, 0.5, 2, 3), MatchFeatures(0.3, 0.6, 0.4, 0.6, 0.5, 1, 1)]

    predictions = predict_batch(artifact, features_list)

    assert len(predictions) == 2
    assert predictions[0].home_win_prob == 0.7
    assert predictions[0].predicted_home_score == 105.0
    assert predictions[0].confidence == "High"
    assert predictions[1].home_win_prob == 0.4
    assert predictions[1].away_win_prob == 0.6
    assert predictions[1].predicted_home_score == 90.0

    # classifier.predict_proba and both regressors were each called exactly
    # once (batched), not once per match.
    assert classifier.predict_proba.call_count == 1
    assert regressor_home.predict.call_count == 1
    assert regressor_away.predict.call_count == 1
    assert len(classifier.predict_proba.call_args[0][0]) == 2  # one call, 2 rows


def test_predict_batch_returns_empty_list_for_no_features():
    assert predict_batch({"classifier": None, "regressor_home": None, "regressor_away": None,
                           "feature_columns": [], "labels": ["H", "A"]}, []) == []
