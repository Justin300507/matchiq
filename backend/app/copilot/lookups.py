from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models_db import Match, Team
from app.utils.name_matching import names_match


def find_team_by_name(db: Session, team_name: str, sport: str) -> Team | None:
    teams = db.query(Team).filter(Team.sport == sport).all()
    for team in teams:
        if names_match(team_name, team.name):
            return team
    return None


def find_upcoming_match(db: Session, home_team: str, away_team: str, sport: str) -> Match | None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    matches = (
        db.query(Match)
        .filter(Match.sport == sport, Match.status == "scheduled", Match.date >= now)
        .order_by(Match.date.asc())
        .all()
    )
    for match in matches:
        home_name, away_name = match.home_team.name, match.away_team.name
        if (names_match(home_team, home_name) and names_match(away_team, away_name)) or (
            names_match(home_team, away_name) and names_match(away_team, home_name)
        ):
            return match
    return None
