from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.features.build_features import build_training_dataframe
from app.ml.baseline import evaluate, naive_home_favorite_probs
from app.ml.calibration import ReliabilityBin, compute_calibration_diagnostics


@dataclass
class BacktestResult:
    sport: str
    predictions_evaluated: int
    model_accuracy: float
    model_log_loss: float
    model_brier_score: float
    baseline_accuracy: float
    baseline_log_loss: float
    baseline_brier_score: float
    labels: list[str] = field(default_factory=list)
    confusion_matrix: list[list[int]] = field(default_factory=list)
    # None when undefined (held-out set has <2 distinct actual outcomes),
    # not zero — a real absence of signal, not a bad score.
    roc_auc: float | None = None
    reliability_bins: list[ReliabilityBin] = field(default_factory=list)


def run_backtest(db: Session, sport: str, artifact: dict) -> BacktestResult:
    """Evaluates the currently-loaded artifact against the same held-out
    (most-recent 20%, time-ordered) split used at training time — this is
    a genuine backtest, not a log of predictions actually served, since
    MatchIQ doesn't yet persist a prediction history table."""
    labels = artifact["labels"]

    df = build_training_dataframe(db, sport)
    if not df.empty:
        df = df.sort_values("date").reset_index(drop=True)
        df = df[df["result"].isin(labels)].reset_index(drop=True)

    split_idx = int(len(df) * 0.8)
    test_df = df.iloc[split_idx:]

    if len(test_df) == 0:
        return BacktestResult(
            sport=sport, predictions_evaluated=0,
            model_accuracy=0.0, model_log_loss=0.0, model_brier_score=0.0,
            baseline_accuracy=0.0, baseline_log_loss=0.0, baseline_brier_score=0.0,
            labels=labels,
        )

    X_test = test_df[artifact["feature_columns"]]
    y_test = list(test_df["result"])

    proba = artifact["classifier"].predict_proba(X_test)
    model_probs = [dict(zip(labels, row)) for row in proba]
    model_metrics = evaluate(y_test, model_probs, labels)

    baseline_probs = naive_home_favorite_probs(len(y_test), sport)
    baseline_metrics = evaluate(y_test, baseline_probs, labels)

    diagnostics = compute_calibration_diagnostics(y_test, model_probs, labels)

    return BacktestResult(
        sport=sport,
        predictions_evaluated=len(test_df),
        model_accuracy=model_metrics["accuracy"],
        model_log_loss=model_metrics["log_loss"],
        model_brier_score=model_metrics["brier_score"],
        baseline_accuracy=baseline_metrics["accuracy"],
        baseline_log_loss=baseline_metrics["log_loss"],
        baseline_brier_score=baseline_metrics["brier_score"],
        labels=diagnostics.labels,
        confusion_matrix=diagnostics.confusion_matrix,
        roc_auc=diagnostics.roc_auc,
        reliability_bins=diagnostics.reliability_bins,
    )
