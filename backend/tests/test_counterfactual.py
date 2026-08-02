from unittest.mock import MagicMock

import numpy as np
import pytest

from app.features.build_features import MatchFeatures
from app.ml.counterfactual import VALID_FEATURES, apply_overrides, simulate_counterfactual

FEATURE_COLUMNS = [
    "home_form_last5", "away_form_last5", "home_win_rate_home",
    "away_win_rate_away", "h2h_home_win_rate", "home_rest_days", "away_rest_days",
]


def test_apply_overrides_replaces_only_specified_fields():
    base = MatchFeatures(0.5, 0.5, 0.5, 0.5, 0.5, 2, 2)

    modified = apply_overrides(base, {"home_form_last5": 0.9})

    assert modified.home_form_last5 == 0.9
    assert modified.away_form_last5 == 0.5
    assert modified.home_rest_days == 2


def test_apply_overrides_rejects_unknown_feature():
    base = MatchFeatures(0.5, 0.5, 0.5, 0.5, 0.5, 2, 2)

    with pytest.raises(ValueError):
        apply_overrides(base, {"opponent_missing_striker": 1.0})


def test_valid_features_matches_match_features_fields():
    assert VALID_FEATURES == set(FEATURE_COLUMNS)


def test_simulate_counterfactual_returns_original_and_modified_predictions():
    classifier = MagicMock()
    classifier.predict_proba.side_effect = [
        np.array([[0.6, 0.4]]),  # original
        np.array([[0.9, 0.1]]),  # counterfactual, after boosting home form
    ]
    regressor_home = MagicMock()
    regressor_home.predict.return_value = np.array([100.0])
    regressor_away = MagicMock()
    regressor_away.predict.return_value = np.array([95.0])

    artifact = {
        "classifier": classifier,
        "regressor_home": regressor_home,
        "regressor_away": regressor_away,
        "feature_columns": FEATURE_COLUMNS,
        "labels": ["H", "A"],
    }
    features = MatchFeatures(0.5, 0.5, 0.5, 0.5, 0.5, 2, 2)

    original, counterfactual = simulate_counterfactual(artifact, features, {"home_form_last5": 0.95})

    assert original.home_win_prob == 0.6
    assert counterfactual.home_win_prob == 0.9
    assert classifier.predict_proba.call_count == 2
