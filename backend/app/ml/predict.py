from dataclasses import dataclass
from pathlib import Path

import joblib
import pandas as pd

from app.features.build_features import MatchFeatures


@dataclass
class Prediction:
    home_win_prob: float
    draw_prob: float | None
    away_win_prob: float
    predicted_home_score: float
    predicted_away_score: float


def load_latest_artifact(sport: str, artifact_dir: Path) -> dict | None:
    path = Path(artifact_dir) / f"{sport}_latest.joblib"
    if not path.exists():
        return None
    return joblib.load(path)


def predict_match(artifact: dict, features: MatchFeatures) -> Prediction:
    row = pd.DataFrame([features.__dict__])[artifact["feature_columns"]]
    proba = artifact["classifier"].predict_proba(row)[0]
    labels = artifact["labels"]
    probs = dict(zip(labels, proba))

    home_score = float(artifact["regressor_home"].predict(row)[0])
    away_score = float(artifact["regressor_away"].predict(row)[0])

    return Prediction(
        home_win_prob=float(probs["H"]),
        draw_prob=float(probs["D"]) if "D" in probs else None,
        away_win_prob=float(probs["A"]),
        predicted_home_score=home_score,
        predicted_away_score=away_score,
    )
