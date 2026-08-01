from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.features.build_features import compute_features
from app.main import get_artifact_dir, get_db
from app.ml.explain import explain_prediction
from app.ml.predict import load_latest_artifact, predict_match
from app.models_db import Match
from app.schemas import ExplanationFactorOut, ExplanationOut, PredictionOut

router = APIRouter(prefix="/predictions", tags=["predictions"])

PER_LEAGUE_LIMIT = 10
OVERALL_LIMIT = 60


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
def get_upcoming(
    sport: str,
    league: str | None = None,
    db: Session = Depends(get_db),
    artifact_dir=Depends(get_artifact_dir),
):
    artifact = load_latest_artifact(sport, artifact_dir)
    if artifact is None:
        raise HTTPException(status_code=503, detail=f"No trained model available for sport={sport}")

    query = db.query(Match).filter(
        Match.sport == sport,
        Match.status == "scheduled",
        Match.date >= datetime.now(timezone.utc).replace(tzinfo=None),
    )
    if league is not None:
        query = query.filter(Match.league == league)

    matches = query.order_by(Match.date.asc()).limit(2000).all()

    if league is not None:
        # A specific league was requested, so there's nothing to balance
        # against — just take the soonest matches for that league.
        selected = matches[:OVERALL_LIMIT]
    else:
        # Leagues start their seasons on different dates, so a flat date-ordered
        # limit would let whichever league happens to kick off earliest crowd out
        # every other league. Cap how many matches each league contributes before
        # re-sorting, so the dashboard shows a mix rather than one league only.
        per_league_counts: dict[str, int] = {}
        selected = []
        for match in matches:
            count = per_league_counts.get(match.league, 0)
            if count >= PER_LEAGUE_LIMIT:
                continue
            per_league_counts[match.league] = count + 1
            selected.append(match)
            if len(selected) >= OVERALL_LIMIT:
                break

    selected = sorted(selected, key=lambda match: match.date)
    return [_to_prediction_out(match, artifact, db) for match in selected]


@router.get("/{game_id}", response_model=PredictionOut)
def get_prediction(game_id: int, db: Session = Depends(get_db), artifact_dir=Depends(get_artifact_dir)):
    match = db.query(Match).filter(Match.id == game_id).one_or_none()
    if match is None:
        raise HTTPException(status_code=404, detail="Game not found")

    artifact = load_latest_artifact(match.sport, artifact_dir)
    if artifact is None:
        raise HTTPException(status_code=503, detail=f"No trained model available for sport={match.sport}")

    return _to_prediction_out(match, artifact, db)


@router.get("/{game_id}/explain", response_model=ExplanationOut)
def get_explanation(game_id: int, db: Session = Depends(get_db), artifact_dir=Depends(get_artifact_dir)):
    match = db.query(Match).filter(Match.id == game_id).one_or_none()
    if match is None:
        raise HTTPException(status_code=404, detail="Game not found")

    artifact = load_latest_artifact(match.sport, artifact_dir)
    if artifact is None:
        raise HTTPException(status_code=503, detail=f"No trained model available for sport={match.sport}")

    features = compute_features(db, match)
    explanation = explain_prediction(artifact, features)
    return ExplanationOut(
        game_id=match.id,
        factors=[
            ExplanationFactorOut(name=f.name, label=f.label, relative_influence_pct=f.relative_influence_pct)
            for f in explanation.factors
        ],
        model_confidence=explanation.model_confidence,
    )
