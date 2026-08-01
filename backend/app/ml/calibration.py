from dataclasses import dataclass

import numpy as np
from sklearn.metrics import roc_auc_score

_N_BINS = 10


@dataclass
class ReliabilityBin:
    bin_start: float
    bin_end: float
    avg_confidence: float
    observed_accuracy: float
    count: int


@dataclass
class CalibrationDiagnostics:
    labels: list[str]
    # confusion_matrix[i][j] = count of matches where the actual result was
    # labels[i] and the model's top pick was labels[j].
    confusion_matrix: list[list[int]]
    # None when the held-out set has fewer than two distinct actual outcomes
    # (ROC AUC is undefined in that case, not zero).
    roc_auc: float | None
    reliability_bins: list[ReliabilityBin]


def compute_calibration_diagnostics(
    y_true: list[str], model_probs: list[dict[str, float]], labels: list[str]
) -> CalibrationDiagnostics:
    if not y_true:
        return CalibrationDiagnostics(labels=labels, confusion_matrix=[], roc_auc=None, reliability_bins=[])

    prob_matrix = np.array([[probs.get(label, 0.0) for label in labels] for probs in model_probs])
    predicted_idx = np.argmax(prob_matrix, axis=1)
    predicted_labels = [labels[i] for i in predicted_idx]

    label_index = {label: i for i, label in enumerate(labels)}
    confusion = [[0] * len(labels) for _ in labels]
    for actual, predicted in zip(y_true, predicted_labels):
        confusion[label_index[actual]][label_index[predicted]] += 1

    return CalibrationDiagnostics(
        labels=labels,
        confusion_matrix=confusion,
        roc_auc=_compute_roc_auc(y_true, prob_matrix, labels),
        reliability_bins=_compute_reliability_bins(y_true, predicted_labels, prob_matrix, predicted_idx),
    )


def _compute_roc_auc(y_true: list[str], prob_matrix: np.ndarray, labels: list[str]) -> float | None:
    y_true_idx = [labels.index(label) for label in y_true]
    if len(set(y_true_idx)) < 2:
        return None
    try:
        if len(labels) == 2:
            return float(roc_auc_score(y_true_idx, prob_matrix[:, 1]))
        return float(roc_auc_score(y_true_idx, prob_matrix, multi_class="ovr", labels=list(range(len(labels)))))
    except ValueError:
        return None


def _compute_reliability_bins(
    y_true: list[str],
    predicted_labels: list[str],
    prob_matrix: np.ndarray,
    predicted_idx: np.ndarray,
) -> list[ReliabilityBin]:
    # "Confidence calibration": bin every prediction by how confident the
    # model was in its top pick, then check what fraction of predictions in
    # that bin were actually correct. Works the same way for a 2-way (NBA)
    # or 3-way (soccer) model, unlike a binary-only reliability curve.
    confidences = prob_matrix[np.arange(len(prob_matrix)), predicted_idx]
    correct = np.array([1.0 if actual == pred else 0.0 for actual, pred in zip(y_true, predicted_labels)])

    bins: list[ReliabilityBin] = []
    edges = np.linspace(0.0, 1.0, _N_BINS + 1)
    for i in range(_N_BINS):
        bin_start, bin_end = edges[i], edges[i + 1]
        if i == _N_BINS - 1:
            mask = (confidences >= bin_start) & (confidences <= bin_end)
        else:
            mask = (confidences >= bin_start) & (confidences < bin_end)
        count = int(mask.sum())
        if count == 0:
            continue
        bins.append(ReliabilityBin(
            bin_start=float(bin_start),
            bin_end=float(bin_end),
            avg_confidence=float(confidences[mask].mean()),
            observed_accuracy=float(correct[mask].mean()),
            count=count,
        ))
    return bins
