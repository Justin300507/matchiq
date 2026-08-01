from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.features.build_features import compute_features
from app.main import get_artifact_dir, get_db
from app.ml.predict import load_latest_artifact, predict_match
from app.models_db import Match
from app.schemas import PredictionOut

router = APIRouter(prefix="/predictions", tags=["predictions"])


def _to_prediction_out(match: Match, artifact: dict, db: Session) -> PredictionOut:
    features = compute_features(db, match)
    prediction = predict_match(artifact, features)
    return PredictionOut(
        game_id=match.id,
        sport=match.sport,
        league=match.league,
        date=match.date,
        home_team=match.home_team,
        away_team=match.away_team,
        home_win_prob=prediction.home_win_prob,
        draw_prob=prediction.draw_prob,
        away_win_prob=prediction.away_win_prob,
        predicted_home_score=prediction.predicted_home_score,
        predicted_away_score=prediction.predicted_away_score,
    )


@router.get("/upcoming", response_model=list[PredictionOut])
def get_upcoming(sport: str, db: Session = Depends(get_db), artifact_dir=Depends(get_artifact_dir)):
    artifact = load_latest_artifact(sport, artifact_dir)
    if artifact is None:
        raise HTTPException(status_code=503, detail=f"No trained model available for sport={sport}")

    matches = (
        db.query(Match)
        .filter(Match.sport == sport, Match.status == "scheduled", Match.date >= datetime.now(timezone.utc).replace(tzinfo=None))
        .order_by(Match.date.asc())
        .limit(50)
        .all()
    )
    return [_to_prediction_out(match, artifact, db) for match in matches]


@router.get("/{game_id}", response_model=PredictionOut)
def get_prediction(game_id: int, db: Session = Depends(get_db), artifact_dir=Depends(get_artifact_dir)):
    match = db.query(Match).filter(Match.id == game_id).one_or_none()
    if match is None:
        raise HTTPException(status_code=404, detail="Game not found")

    artifact = load_latest_artifact(match.sport, artifact_dir)
    if artifact is None:
        raise HTTPException(status_code=503, detail=f"No trained model available for sport={match.sport}")

    return _to_prediction_out(match, artifact, db)
