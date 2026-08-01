from collections import Counter
from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.features.build_features import MatchFeatures

# Fallback only for artifacts trained before home_score_std/away_score_std
# were tracked — real artifacts always carry the empirical value.
_DEFAULT_SCORE_STD = 8.0


@dataclass
class ScorelineResult:
    home_score: int
    away_score: int
    frequency_pct: float


@dataclass
class SimulationResult:
    home_win_pct: float
    draw_pct: float | None
    away_win_pct: float
    top_scorelines: list[ScorelineResult]
    n_simulations: int


def simulate_match(artifact: dict, features: MatchFeatures, n_simulations: int = 10000, rng=None) -> SimulationResult:
    rng = rng or np.random.default_rng()
    row = pd.DataFrame([features.__dict__])[artifact["feature_columns"]]

    predicted_home = float(artifact["regressor_home"].predict(row)[0])
    predicted_away = float(artifact["regressor_away"].predict(row)[0])
    home_std = max(float(artifact.get("home_score_std") or _DEFAULT_SCORE_STD), 0.5)
    away_std = max(float(artifact.get("away_score_std") or _DEFAULT_SCORE_STD), 0.5)

    home_scores = np.clip(np.round(rng.normal(predicted_home, home_std, n_simulations)), 0, None).astype(int)
    away_scores = np.clip(np.round(rng.normal(predicted_away, away_std, n_simulations)), 0, None).astype(int)

    has_draws = "D" in artifact["labels"]
    if not has_draws:
        # This sport has no draw outcome (e.g. basketball) — a tied
        # simulated score is a coin-flip in real overtime, not a draw.
        tie_idx = np.where(home_scores == away_scores)[0]
        winners_home = rng.integers(0, 2, size=len(tie_idx)) == 0
        home_scores[tie_idx[winners_home]] += 1
        away_scores[tie_idx[~winners_home]] += 1

    home_wins = home_scores > away_scores
    away_wins = away_scores > home_scores
    draws = home_scores == away_scores

    counter = Counter(zip(home_scores.tolist(), away_scores.tolist()))
    top_scorelines = [
        ScorelineResult(home_score=h, away_score=a, frequency_pct=count / n_simulations * 100)
        for (h, a), count in counter.most_common(5)
    ]

    return SimulationResult(
        home_win_pct=float(home_wins.mean() * 100),
        draw_pct=float(draws.mean() * 100) if has_draws else None,
        away_win_pct=float(away_wins.mean() * 100),
        top_scorelines=top_scorelines,
        n_simulations=n_simulations,
    )
