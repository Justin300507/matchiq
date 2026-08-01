from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.main import get_artifact_dir, get_db
from app.ml.backtest import run_backtest
from app.ml.predict import load_latest_artifact
from app.schemas import BacktestOut

router = APIRouter(prefix="/accuracy", tags=["accuracy"])


@router.get("", response_model=BacktestOut)
def get_accuracy(sport: str, db: Session = Depends(get_db), artifact_dir=Depends(get_artifact_dir)):
    artifact = load_latest_artifact(sport, artifact_dir)
    if artifact is None:
        raise HTTPException(status_code=503, detail=f"No trained model available for sport={sport}")

    result = run_backtest(db, sport, artifact)
    return BacktestOut(
        sport=result.sport,
        predictions_evaluated=result.predictions_evaluated,
        model_accuracy=result.model_accuracy,
        model_log_loss=result.model_log_loss,
        model_brier_score=result.model_brier_score,
        baseline_accuracy=result.baseline_accuracy,
        baseline_log_loss=result.baseline_log_loss,
        baseline_brier_score=result.baseline_brier_score,
    )
