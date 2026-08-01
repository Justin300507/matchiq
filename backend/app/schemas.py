from datetime import datetime

from pydantic import BaseModel


class TeamOut(BaseModel):
    id: int
    name: str
    league: str

    class Config:
        from_attributes = True


class PredictionOut(BaseModel):
    game_id: int
    sport: str
    league: str
    date: datetime
    home_team: TeamOut
    away_team: TeamOut
    home_win_prob: float
    draw_prob: float | None
    away_win_prob: float
    predicted_home_score: float
    predicted_away_score: float
    model_confidence: str


class ExplanationFactorOut(BaseModel):
    name: str
    label: str
    relative_influence_pct: float


class ExplanationOut(BaseModel):
    game_id: int
    factors: list[ExplanationFactorOut]
    model_confidence: str


class ScorelineOut(BaseModel):
    home_score: int
    away_score: int
    frequency_pct: float


class SimulationOut(BaseModel):
    game_id: int
    home_win_pct: float
    draw_pct: float | None
    away_win_pct: float
    top_scorelines: list[ScorelineOut]
    n_simulations: int


class RecentResultOut(BaseModel):
    date: str
    opponent_name: str
    is_home: bool
    team_score: int
    opponent_score: int
    result: str


class MatchContextOut(BaseModel):
    game_id: int
    home_recent_form: list[RecentResultOut]
    away_recent_form: list[RecentResultOut]
    head_to_head: list[RecentResultOut]


class PredictionSummaryOut(BaseModel):
    home_win_prob: float
    draw_prob: float | None
    away_win_prob: float
    predicted_home_score: float
    predicted_away_score: float
    model_confidence: str


class WhatIfOut(BaseModel):
    game_id: int
    overrides_applied: dict[str, float]
    original: PredictionSummaryOut
    counterfactual: PredictionSummaryOut


class ReliabilityBinOut(BaseModel):
    bin_start: float
    bin_end: float
    avg_confidence: float
    observed_accuracy: float
    count: int


class BacktestOut(BaseModel):
    sport: str
    predictions_evaluated: int
    model_accuracy: float
    model_log_loss: float
    model_brier_score: float
    baseline_accuracy: float
    baseline_log_loss: float
    baseline_brier_score: float
    labels: list[str]
    confusion_matrix: list[list[int]]
    roc_auc: float | None
    reliability_bins: list[ReliabilityBinOut]


class TeamProfileOut(BaseModel):
    team_id: int
    team_name: str
    league: str
    matches_played: int
    wins: int
    draws: int
    losses: int
    goals_for_avg: float
    goals_against_avg: float
    home_win_rate: float
    away_win_rate: float
    last5_form: str
    elo_rating: float


class ChatRequest(BaseModel):
    sport: str
    league: str | None = None
    question: str


class ChatResponse(BaseModel):
    answer: str
