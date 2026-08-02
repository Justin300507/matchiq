from dataclasses import dataclass

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.ml.elo import DEFAULT_RATING, compute_elo_ratings
from app.models_db import Match, Team


@dataclass
class TeamProfile:
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


def _result_for_team(match: Match, team_id: int) -> str:
    if match.home_team_id == team_id:
        home_score, away_score = match.home_score, match.away_score
    else:
        home_score, away_score = match.away_score, match.home_score
    if home_score > away_score:
        return "W"
    if home_score < away_score:
        return "L"
    return "D"


def compute_team_profile(db: Session, team: Team) -> TeamProfile:
    matches = (
        db.query(Match)
        .filter(
            Match.sport == team.sport,
            Match.status == "final",
            or_(Match.home_team_id == team.id, Match.away_team_id == team.id),
        )
        .order_by(Match.date.asc())
        .all()
    )

    wins = draws = losses = 0
    goals_for = goals_against = 0
    home_matches = home_wins = away_matches = away_wins = 0

    for match in matches:
        is_home = match.home_team_id == team.id
        team_score = match.home_score if is_home else match.away_score
        opp_score = match.away_score if is_home else match.home_score
        goals_for += team_score
        goals_against += opp_score

        result = _result_for_team(match, team.id)
        if result == "W":
            wins += 1
        elif result == "L":
            losses += 1
        else:
            draws += 1

        if is_home:
            home_matches += 1
            home_wins += 1 if result == "W" else 0
        else:
            away_matches += 1
            away_wins += 1 if result == "W" else 0

    matches_played = len(matches)
    last5_form = "".join(_result_for_team(m, team.id) for m in matches[-5:])

    elo_ratings = compute_elo_ratings(db, team.sport)
    elo_rating = elo_ratings.get(team.id, DEFAULT_RATING)

    return TeamProfile(
        team_id=team.id,
        team_name=team.name,
        league=team.league,
        matches_played=matches_played,
        wins=wins,
        draws=draws,
        losses=losses,
        goals_for_avg=goals_for / matches_played if matches_played else 0.0,
        goals_against_avg=goals_against / matches_played if matches_played else 0.0,
        home_win_rate=home_wins / home_matches if home_matches else 0.0,
        away_win_rate=away_wins / away_matches if away_matches else 0.0,
        last5_form=last5_form,
        elo_rating=elo_rating,
    )
