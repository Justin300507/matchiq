from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.main import get_db
from app.models_db import Team
from app.schemas import TeamOut

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("/{team_id}", response_model=TeamOut)
def get_team(team_id: int, db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.id == team_id).one_or_none()
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    return team
