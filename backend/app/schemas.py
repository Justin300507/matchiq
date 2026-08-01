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


class ExplanationFactorOut(BaseModel):
    name: str
    label: str
    relative_influence_pct: float


class ExplanationOut(BaseModel):
    game_id: int
    factors: list[ExplanationFactorOut]
    model_confidence: str
