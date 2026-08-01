from unittest.mock import MagicMock

import numpy as np

from app.features.build_features import MatchFeatures
from app.ml.simulate import simulate_match

FEATURE_COLUMNS = [
    "home_form_last5", "away_form_last5", "home_win_rate_home",
    "away_win_rate_away", "h2h_home_win_rate", "home_rest_days", "away_rest_days",
]


def _mock_artifact(labels, home_score_std=1.0, away_score_std=1.0, predicted_home=2.0, predicted_away=1.0):
    regressor_home = MagicMock()
    regressor_home.predict.return_value = np.array([predicted_home])
    regressor_away = MagicMock()
    regressor_away.predict.return_value = np.array([predicted_away])
    return {
        "regressor_home": regressor_home,
        "regressor_away": regressor_away,
        "feature_columns": FEATURE_COLUMNS,
        "labels": labels,
        "home_score_std": home_score_std,
        "away_score_std": away_score_std,
    }


def test_simulate_match_probabilities_sum_to_100_with_draws():
    artifact = _mock_artifact(["H", "D", "A"])
    features = MatchFeatures(0.6, 0.4, 0.7, 0.5, 0.5, 2, 3)

    result = simulate_match(artifact, features, n_simulations=2000, rng=np.random.default_rng(42))

    assert result.draw_pct is not None
    total = result.home_win_pct + result.draw_pct + result.away_win_pct
    assert abs(total - 100.0) < 0.01
    assert result.n_simulations == 2000


def test_simulate_match_has_no_draw_outcome_for_binary_sport():
    artifact = _mock_artifact(["H", "A"])
    features = MatchFeatures(0.6, 0.4, 0.7, 0.5, 0.5, 2, 3)

    result = simulate_match(artifact, features, n_simulations=2000, rng=np.random.default_rng(42))

    assert result.draw_pct is None
    assert abs((result.home_win_pct + result.away_win_pct) - 100.0) < 0.01


def test_simulate_match_top_scorelines_sorted_by_frequency_descending():
    artifact = _mock_artifact(["H", "D", "A"], home_score_std=0.3, away_score_std=0.3)
    features = MatchFeatures(0.6, 0.4, 0.7, 0.5, 0.5, 2, 3)

    result = simulate_match(artifact, features, n_simulations=2000, rng=np.random.default_rng(42))

    frequencies = [s.frequency_pct for s in result.top_scorelines]
    assert frequencies == sorted(frequencies, reverse=True)
    assert len(result.top_scorelines) <= 5
    # With a tight std around predicted (2.0, 1.0), the 2-1 scoreline should
    # dominate.
    assert result.top_scorelines[0].home_score == 2
    assert result.top_scorelines[0].away_score == 1


def test_simulate_match_never_returns_negative_scores():
    artifact = _mock_artifact(["H", "A"], predicted_home=0.2, predicted_away=0.1, home_score_std=5.0, away_score_std=5.0)
    features = MatchFeatures(0.6, 0.4, 0.7, 0.5, 0.5, 2, 3)

    result = simulate_match(artifact, features, n_simulations=2000, rng=np.random.default_rng(42))

    for scoreline in result.top_scorelines:
        assert scoreline.home_score >= 0
        assert scoreline.away_score >= 0
