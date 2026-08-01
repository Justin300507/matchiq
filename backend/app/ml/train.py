from pathlib import Path

import joblib
import numpy as np
from sklearn.model_selection import train_test_split
from sqlalchemy.orm import Session
from xgboost import XGBClassifier, XGBRegressor

from app.features.build_features import build_training_dataframe
from app.ml.baseline import evaluate, naive_home_favorite_probs

FEATURE_COLUMNS = [
    "home_form_last5",
    "away_form_last5",
    "home_win_rate_home",
    "away_win_rate_away",
    "h2h_home_win_rate",
    "home_rest_days",
    "away_rest_days",
]


def _labels_for_sport(sport: str) -> list[str]:
    return ["H", "D", "A"] if sport == "soccer" else ["H", "A"]


def train_sport_models(db: Session, sport: str, artifact_dir: Path) -> dict:
    df = build_training_dataframe(db, sport)
    df = df.sort_values("date").reset_index(drop=True)
    labels = _labels_for_sport(sport)
    # A sport with only H/A labels (e.g. nba) has no draw outcome; drop any
    # tied-score rows that don't fit the label space rather than feeding the
    # classifier a class it can't predict.
    df = df[df["result"].isin(labels)].reset_index(drop=True)

    split_idx = int(len(df) * 0.8)
    train_df, test_df = df.iloc[:split_idx], df.iloc[split_idx:]

    X_train, X_test = train_df[FEATURE_COLUMNS], test_df[FEATURE_COLUMNS]
    y_train = train_df["result"].map({label: i for i, label in enumerate(labels)})
    y_test = test_df["result"]

    classifier = XGBClassifier(n_estimators=100, max_depth=3, eval_metric="mlogloss" if sport == "soccer" else "logloss")
    classifier.fit(X_train, y_train)

    regressor_home = XGBRegressor(n_estimators=100, max_depth=3)
    regressor_home.fit(X_train, train_df["home_score"])
    regressor_away = XGBRegressor(n_estimators=100, max_depth=3)
    regressor_away.fit(X_train, train_df["away_score"])

    proba = classifier.predict_proba(X_test)
    model_probs = [dict(zip(labels, row)) for row in proba]
    model_metrics = evaluate(list(y_test), model_probs, labels)

    baseline_probs = naive_home_favorite_probs(len(y_test), sport)
    baseline_metrics = evaluate(list(y_test), baseline_probs, labels)

    beat_baseline = model_metrics["log_loss"] < baseline_metrics["log_loss"]

    artifact_path = None
    if beat_baseline:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifact_dir / f"{sport}_latest.joblib"
        joblib.dump(
            {
                "classifier": classifier,
                "regressor_home": regressor_home,
                "regressor_away": regressor_away,
                "feature_columns": FEATURE_COLUMNS,
                "labels": labels,
            },
            artifact_path,
        )

    return {
        "model_metrics": model_metrics,
        "baseline_metrics": baseline_metrics,
        "beat_baseline": beat_baseline,
        "artifact_path": str(artifact_path) if artifact_path else None,
    }
