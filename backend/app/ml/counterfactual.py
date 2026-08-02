from dataclasses import replace

from app.features.build_features import MatchFeatures
from app.ml.predict import Prediction, predict_match

# The only "what-if" levers MatchIQ can honestly offer are the features the
# model actually uses — form, home/away splits, head-to-head, rest days.
# There's no injury, weather, or in-match event data to perturb, so this is
# deliberately scoped to feature-level counterfactuals rather than the
# broader "what if a player is ruled out" style digital twin.
VALID_FEATURES = {
    "home_form_last5", "away_form_last5", "home_win_rate_home",
    "away_win_rate_away", "h2h_home_win_rate", "home_rest_days", "away_rest_days",
}


def apply_overrides(features: MatchFeatures, overrides: dict[str, float]) -> MatchFeatures:
    unknown = set(overrides) - VALID_FEATURES
    if unknown:
        raise ValueError(f"Unknown feature(s): {sorted(unknown)}")
    return replace(features, **overrides)


def simulate_counterfactual(
    artifact: dict, features: MatchFeatures, overrides: dict[str, float]
) -> tuple[Prediction, Prediction]:
    # Validate before doing any real work, so a bad feature name fails fast
    # without requiring a fully-populated artifact.
    modified_features = apply_overrides(features, overrides)
    original = predict_match(artifact, features)
    counterfactual = predict_match(artifact, modified_features)
    return original, counterfactual
