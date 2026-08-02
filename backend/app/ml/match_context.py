from dataclasses import dataclass

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models_db import Match


@dataclass
class RecentResult:
    date: str
    opponent_name: str
    is_home: bool
    team_score: int
    opponent_score: int
    result: str  # "W" | "D" | "L"


@dataclass
class MatchContext:
    home_recent_form: list[RecentResult]
    away_recent_form: list[RecentResult]
    head_to_head: list[RecentResult]


def _recent_results(db: Session, sport: str, team_id: int, before_date, limit: int = 10) -> list[RecentResult]:
    matches = (
        db.query(Match)
        .filter(
            Match.sport == sport,
            Match.status == "final",
            Match.date < before_date,
            or_(Match.home_team_id == team_id, Match.away_team_id == team_id),
        )
        .order_by(Match.date.desc())
        .limit(limit)
        .all()
    )

    results = []
    for match in matches:
        is_home = match.home_team_id == team_id
        team_score = match.home_score if is_home else match.away_score
        opp_score = match.away_score if is_home else match.home_score
        opponent = match.away_team if is_home else match.home_team
        if team_score > opp_score:
            result = "W"
        elif team_score < opp_score:
            result = "L"
        else:
            result = "D"
        results.append(RecentResult(
            date=match.date.isoformat(),
            opponent_name=opponent.name,
            is_home=is_home,
            team_score=team_score,
            opponent_score=opp_score,
            result=result,
        ))
    return results


def _head_to_head(db: Session, sport: str, home_id: int, away_id: int, before_date, limit: int = 10) -> list[RecentResult]:
    matches = (
        db.query(Match)
        .filter(
            Match.sport == sport,
            Match.status == "final",
            Match.date < before_date,
            or_(
                (Match.home_team_id == home_id) & (Match.away_team_id == away_id),
                (Match.home_team_id == away_id) & (Match.away_team_id == home_id),
            ),
        )
        .order_by(Match.date.desc())
        .limit(limit)
        .all()
    )

    results = []
    for match in matches:
        is_home = match.home_team_id == home_id
        team_score = match.home_score if is_home else match.away_score
        opp_score = match.away_score if is_home else match.home_score
        opponent = match.away_team if is_home else match.home_team
        if team_score > opp_score:
            result = "W"
        elif team_score < opp_score:
            result = "L"
        else:
            result = "D"
        results.append(RecentResult(
            date=match.date.isoformat(),
            opponent_name=opponent.name,
            is_home=is_home,
            team_score=team_score,
            opponent_score=opp_score,
            result=result,
        ))
    return results


def compute_match_context(db: Session, match: Match) -> MatchContext:
    return MatchContext(
        home_recent_form=_recent_results(db, match.sport, match.home_team_id, match.date),
        away_recent_form=_recent_results(db, match.sport, match.away_team_id, match.date),
        head_to_head=_head_to_head(db, match.sport, match.home_team_id, match.away_team_id, match.date),
    )
