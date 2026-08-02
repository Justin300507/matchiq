from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from app.features.build_features import MatchFeatures


@dataclass
class Prediction:
    home_win_prob: float
    draw_prob: float | None
    away_win_prob: float
    predicted_home_score: float
    predicted_away_score: float
    confidence: str


def confidence_label(top_prob: float, num_classes: int) -> str:
    """High/Medium/Low based on how far the top predicted probability sits
    above the naive baseline (50% for 2-way, 33% for 3-way outcomes)."""
    if num_classes == 2:
        if top_prob >= 0.65:
            return "High"
        if top_prob >= 0.55:
            return "Medium"
        return "Low"
    if top_prob >= 0.55:
        return "High"
    if top_prob >= 0.40:
        return "Medium"
    return "Low"


# Deserializing a trained artifact (XGBoost classifier + 2 regressors) from
# disk takes ~1s, and this is called on every predictions-related request —
# including several times per match page. Cache by (path, mtime) so a
# retrain (which changes the file's mtime) is picked up automatically, with
# no request paying the reload cost until the next artifact actually exists.
_artifact_cache: dict[tuple[str, float], dict] = {}


def load_latest_artifact(sport: str, artifact_dir: Path) -> dict | None:
    path = Path(artifact_dir) / f"{sport}_latest.joblib"
    if not path.exists():
        return None

    cache_key = (str(path), path.stat().st_mtime)
    cached = _artifact_cache.get(cache_key)
    if cached is not None:
        return cached

    artifact = joblib.load(path)
    for stale_key in [key for key in _artifact_cache if key[0] == str(path)]:
        del _artifact_cache[stale_key]
    _artifact_cache[cache_key] = artifact
    return artifact


def predict_match(artifact: dict, features: MatchFeatures) -> Prediction:
    return predict_batch(artifact, [features])[0]


def predict_batch(artifact: dict, features_list: list[MatchFeatures]) -> list[Prediction]:
    """Predicts many matches in one call instead of one XGBoost predict()
    call per match. Each individual .predict()/.predict_proba() call carries
    real fixed overhead regardless of row count, so calling it once per
    match in a loop (e.g. for a 60-match upcoming list) is dramatically
    slower than building one batch and calling it 3 times total."""
    if not features_list:
        return []

    rows = pd.DataFrame([f.__dict__ for f in features_list])[artifact["feature_columns"]]
    proba_matrix = artifact["classifier"].predict_proba(rows)
    labels = artifact["labels"]
    home_scores = artifact["regressor_home"].predict(rows)
    away_scores = artifact["regressor_away"].predict(rows)

    predictions = []
    for i in range(len(features_list)):
        proba = proba_matrix[i]
        probs = dict(zip(labels, proba))
        predictions.append(Prediction(
            home_win_prob=float(probs["H"]),
            draw_prob=float(probs["D"]) if "D" in probs else None,
            away_win_prob=float(probs["A"]),
            predicted_home_score=float(home_scores[i]),
            predicted_away_score=float(away_scores[i]),
            confidence=confidence_label(float(np.max(proba)), len(labels)),
        ))
    return predictions
