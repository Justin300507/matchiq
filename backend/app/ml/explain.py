from dataclasses import dataclass

import numpy as np
import pandas as pd
import shap

from app.features.build_features import MatchFeatures

_FEATURE_LABELS = {
    "home_form_last5": "Home team's recent form",
    "away_form_last5": "Away team's recent form",
    "home_win_rate_home": "Home team's home advantage",
    "away_win_rate_away": "Away team's away form",
    "h2h_home_win_rate": "Head-to-head history",
    "home_rest_days": "Home team's rest advantage",
    "away_rest_days": "Away team's rest advantage",
}


@dataclass
class ExplanationFactor:
    name: str
    label: str
    relative_influence_pct: float


@dataclass
class Explanation:
    factors: list[ExplanationFactor]
    model_confidence: str


def _confidence_label(top_prob: float, num_classes: int) -> str:
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


def explain_prediction(artifact: dict, features: MatchFeatures) -> Explanation:
    row = pd.DataFrame([features.__dict__])[artifact["feature_columns"]]
    classifier = artifact["classifier"]
    labels: list[str] = artifact["labels"]
    home_idx = labels.index("H")

    explainer = shap.TreeExplainer(classifier)
    raw_shap = np.array(explainer.shap_values(row))

    if raw_shap.ndim == 2:
        # Binary classifier: shap_values are margin-space contributions
        # toward the positive class (label index 1). Since a binary
        # logit's margin for class 0 is exactly the negation of class 1's
        # margin, negating gives an exact (not approximated) decomposition
        # toward the home-win side when "H" is label index 0.
        per_feature = raw_shap[0]
        if home_idx != 1:
            per_feature = -per_feature
    else:
        # Multiclass: shape is (samples, features, classes).
        per_feature = raw_shap[0, :, home_idx]

    total_abs = float(np.abs(per_feature).sum())
    factors = [
        ExplanationFactor(
            name=column,
            label=_FEATURE_LABELS.get(column, column),
            # SHAP values for tree models are additive in margin (log-odds)
            # space, not probability space, and multiclass probability-space
            # decomposition isn't supported by this model/shap combination —
            # so each factor's share is reported as a normalized relative
            # influence on the home-win margin, not a literal probability
            # percentage-point.
            relative_influence_pct=0.0 if total_abs == 0 else float(value) / total_abs * 100,
        )
        for column, value in zip(artifact["feature_columns"], per_feature)
    ]
    factors.sort(key=lambda f: abs(f.relative_influence_pct), reverse=True)

    proba = classifier.predict_proba(row)[0]
    confidence = _confidence_label(float(max(proba)), len(labels))

    return Explanation(factors=factors, model_confidence=confidence)
