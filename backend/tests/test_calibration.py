from app.ml.calibration import compute_calibration_diagnostics


def test_confusion_matrix_counts_actual_vs_predicted():
    y_true = ["H", "H", "A", "A", "A"]
    model_probs = [
        {"H": 0.9, "A": 0.1},  # actual H, predicted H
        {"H": 0.4, "A": 0.6},  # actual H, predicted A (miss)
        {"H": 0.2, "A": 0.8},  # actual A, predicted A
        {"H": 0.7, "A": 0.3},  # actual A, predicted H (miss)
        {"H": 0.3, "A": 0.7},  # actual A, predicted A
    ]
    labels = ["H", "A"]

    diagnostics = compute_calibration_diagnostics(y_true, model_probs, labels)

    assert diagnostics.labels == ["H", "A"]
    # rows = actual (H, A); cols = predicted (H, A)
    assert diagnostics.confusion_matrix == [[1, 1], [1, 2]]


def test_roc_auc_is_none_when_only_one_class_present():
    y_true = ["H", "H", "H"]
    model_probs = [{"H": 0.9, "A": 0.1}, {"H": 0.6, "A": 0.4}, {"H": 0.8, "A": 0.2}]

    diagnostics = compute_calibration_diagnostics(y_true, model_probs, ["H", "A"])

    assert diagnostics.roc_auc is None


def test_roc_auc_is_perfect_for_perfectly_separated_predictions():
    y_true = ["H", "H", "A", "A"]
    model_probs = [
        {"H": 0.9, "A": 0.1},
        {"H": 0.8, "A": 0.2},
        {"H": 0.2, "A": 0.8},
        {"H": 0.1, "A": 0.9},
    ]

    diagnostics = compute_calibration_diagnostics(y_true, model_probs, ["H", "A"])

    assert diagnostics.roc_auc == 1.0


def test_reliability_bins_group_by_confidence_and_report_observed_accuracy():
    # Four high-confidence (~0.9) predictions, 3 correct, 1 wrong.
    y_true = ["H", "H", "H", "A"]
    model_probs = [
        {"H": 0.9, "A": 0.1},
        {"H": 0.9, "A": 0.1},
        {"H": 0.9, "A": 0.1},
        {"H": 0.9, "A": 0.1},  # actual is A -> wrong, but model was still confident
    ]

    diagnostics = compute_calibration_diagnostics(y_true, model_probs, ["H", "A"])

    assert len(diagnostics.reliability_bins) == 1
    bin_ = diagnostics.reliability_bins[0]
    assert bin_.count == 4
    assert 0.89 <= bin_.avg_confidence <= 0.91
    assert bin_.observed_accuracy == 0.75


def test_returns_empty_diagnostics_for_no_data():
    diagnostics = compute_calibration_diagnostics([], [], ["H", "A"])

    assert diagnostics.confusion_matrix == []
    assert diagnostics.roc_auc is None
    assert diagnostics.reliability_bins == []
