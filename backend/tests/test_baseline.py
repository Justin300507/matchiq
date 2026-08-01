import math

from app.ml.baseline import evaluate, naive_home_favorite_probs


def test_naive_home_favorite_probs_nba():
    probs = naive_home_favorite_probs(3, sport="nba")
    assert probs == [{"H": 1.0, "A": 0.0}] * 3


def test_naive_home_favorite_probs_soccer():
    probs = naive_home_favorite_probs(2, sport="soccer")
    assert probs == [{"H": 1.0, "D": 0.0, "A": 0.0}] * 2


def test_evaluate_perfect_predictions():
    y_true = ["H", "H", "A"]
    y_pred = [{"H": 1.0, "A": 0.0}] * 2 + [{"H": 0.0, "A": 1.0}]

    metrics = evaluate(y_true, y_pred, labels=["H", "A"])

    assert metrics["accuracy"] == 1.0
    assert math.isclose(metrics["log_loss"], 0.0, abs_tol=1e-6)
    assert math.isclose(metrics["brier_score"], 0.0, abs_tol=1e-6)


def test_evaluate_naive_baseline_on_mixed_results():
    y_true = ["H", "A", "H"]
    y_pred = [{"H": 1.0, "A": 0.0}] * 3

    metrics = evaluate(y_true, y_pred, labels=["H", "A"])

    assert math.isclose(metrics["accuracy"], 2 / 3, abs_tol=1e-6)
