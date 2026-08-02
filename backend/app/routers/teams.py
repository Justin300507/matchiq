from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.main import get_db
from app.ml.team_profile import compute_team_profile
from app.models_db import Team
from app.schemas import TeamOut, TeamProfileOut

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("/{team_id}", response_model=TeamOut)
def get_team(team_id: int, db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.id == team_id).one_or_none()
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    return TeamOut.model_validate(team)


@router.get("/{team_id}/profile", response_model=TeamProfileOut)
def get_team_profile(team_id: int, db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.id == team_id).one_or_none()
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")

    profile = compute_team_profile(db, team)
    return TeamProfileOut(
        team_id=profile.team_id,
        team_name=profile.team_name,
        league=profile.league,
        matches_played=profile.matches_played,
        wins=profile.wins,
        draws=profile.draws,
        losses=profile.losses,
        goals_for_avg=profile.goals_for_avg,
        goals_against_avg=profile.goals_against_avg,
        home_win_rate=profile.home_win_rate,
        away_win_rate=profile.away_win_rate,
        last5_form=profile.last5_form,
        elo_rating=profile.elo_rating,
    )
