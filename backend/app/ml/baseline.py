import numpy as np
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss


def naive_home_favorite_probs(n: int, sport: str) -> list[dict]:
    if sport == "soccer":
        return [{"H": 1.0, "D": 0.0, "A": 0.0} for _ in range(n)]
    return [{"H": 1.0, "A": 0.0} for _ in range(n)]


def evaluate(y_true: list[str], y_pred_probs: list[dict], labels: list[str]) -> dict:
    y_true_idx = [labels.index(label) for label in y_true]
    prob_matrix = np.array([[probs.get(label, 0.0) for label in labels] for probs in y_pred_probs])
    predicted_labels = [labels[np.argmax(row)] for row in prob_matrix]

    accuracy = accuracy_score(y_true, predicted_labels)
    loss = log_loss(y_true_idx, prob_matrix, labels=list(range(len(labels))))

    home_true = np.array([1.0 if label == "H" else 0.0 for label in y_true])
    home_pred = prob_matrix[:, labels.index("H")]
    brier = brier_score_loss(home_true, home_pred)

    return {"accuracy": float(accuracy), "log_loss": float(loss), "brier_score": float(brier)}
