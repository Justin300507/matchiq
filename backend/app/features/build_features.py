from collections import defaultdict
from dataclasses import dataclass

import pandas as pd
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models_db import Match


@dataclass
class MatchFeatures:
    home_form_last5: float
    away_form_last5: float
    home_win_rate_home: float
    away_win_rate_away: float
    h2h_home_win_rate: float
    home_rest_days: int
    away_rest_days: int


def _did_team_win(match: Match, team_id: int) -> bool:
    if match.home_team_id == team_id:
        return match.home_score > match.away_score
    return match.away_score > match.home_score


def _team_matches_before(db: Session, sport: str, team_id: int, before_date, limit: int | None = None):
    query = (
        db.query(Match)
        .filter(
            Match.sport == sport,
            Match.status == "final",
            Match.date < before_date,
            or_(Match.home_team_id == team_id, Match.away_team_id == team_id),
        )
        .order_by(Match.date.desc())
    )
    if limit is not None:
        query = query.limit(limit)
    return query.all()


def _form(matches: list[Match], team_id: int) -> float:
    if not matches:
        return 0.5
    wins = sum(1 for m in matches if _did_team_win(m, team_id))
    return wins / len(matches)


def _home_away_win_rate(db: Session, sport: str, team_id: int, before_date, is_home: bool) -> float:
    column = Match.home_team_id if is_home else Match.away_team_id
    matches = (
        db.query(Match)
        .filter(Match.sport == sport, Match.status == "final", Match.date < before_date, column == team_id)
        .all()
    )
    return _form(matches, team_id)


def _rest_days(matches: list[Match], target_date) -> int:
    if not matches:
        return 7
    return (target_date - matches[0].date).days


def _h2h_win_rate(matches: list[Match], home_id: int) -> float:
    if not matches:
        return 0.5
    home_wins = sum(1 for m in matches if _did_team_win(m, home_id))
    return home_wins / len(matches)


def _h2h_home_win_rate(db: Session, sport: str, home_id: int, away_id: int, before_date) -> float:
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
        .all()
    )
    return _h2h_win_rate(matches, home_id)


def compute_features(db: Session, match: Match) -> MatchFeatures:
    home_recent = _team_matches_before(db, match.sport, match.home_team_id, match.date, limit=5)
    away_recent = _team_matches_before(db, match.sport, match.away_team_id, match.date, limit=5)

    return MatchFeatures(
        home_form_last5=_form(home_recent, match.home_team_id),
        away_form_last5=_form(away_recent, match.away_team_id),
        home_win_rate_home=_home_away_win_rate(db, match.sport, match.home_team_id, match.date, is_home=True),
        away_win_rate_away=_home_away_win_rate(db, match.sport, match.away_team_id, match.date, is_home=False),
        h2h_home_win_rate=_h2h_home_win_rate(db, match.sport, match.home_team_id, match.away_team_id, match.date),
        home_rest_days=_rest_days(home_recent, match.date),
        away_rest_days=_rest_days(away_recent, match.date),
    )


def _result(match: Match) -> str:
    if match.home_score > match.away_score:
        return "H"
    if match.home_score < match.away_score:
        return "A"
    return "D"


def _recent_matches_before(ascending_matches: list[Match], before_date, limit: int) -> list[Match]:
    # ascending_matches is already sorted oldest-to-newest, so the most
    # recent `limit` matches before the cutoff are just its tail end.
    # Reversed to match _team_matches_before's DB-side `order_by(desc())`,
    # since _rest_days relies on matches[0] being the most recent.
    filtered = [m for m in ascending_matches if m.date < before_date]
    recent = filtered[-limit:] if limit else filtered
    return list(reversed(recent))


def build_training_dataframe(db: Session, sport: str) -> pd.DataFrame:
    # One query for the whole sport, then compute every match's features
    # from in-memory indices, instead of ~5 DB round trips per match. On a
    # few thousand historical matches this is the difference between a
    # sub-second response and a 60+ second one.
    matches = (
        db.query(Match)
        .filter(Match.sport == sport, Match.status == "final")
        .order_by(Match.date.asc())
        .all()
    )

    matches_by_team: dict[int, list[Match]] = defaultdict(list)
    home_matches_by_team: dict[int, list[Match]] = defaultdict(list)
    away_matches_by_team: dict[int, list[Match]] = defaultdict(list)
    matches_by_pair: dict[frozenset[int], list[Match]] = defaultdict(list)

    for match in matches:
        matches_by_team[match.home_team_id].append(match)
        matches_by_team[match.away_team_id].append(match)
        home_matches_by_team[match.home_team_id].append(match)
        away_matches_by_team[match.away_team_id].append(match)
        matches_by_pair[frozenset((match.home_team_id, match.away_team_id))].append(match)

    rows = []
    for match in matches:
        home_recent = _recent_matches_before(matches_by_team[match.home_team_id], match.date, limit=5)
        away_recent = _recent_matches_before(matches_by_team[match.away_team_id], match.date, limit=5)
        home_history = [m for m in home_matches_by_team[match.home_team_id] if m.date < match.date]
        away_history = [m for m in away_matches_by_team[match.away_team_id] if m.date < match.date]
        h2h_history = [
            m for m in matches_by_pair[frozenset((match.home_team_id, match.away_team_id))] if m.date < match.date
        ]

        features = MatchFeatures(
            home_form_last5=_form(home_recent, match.home_team_id),
            away_form_last5=_form(away_recent, match.away_team_id),
            home_win_rate_home=_form(home_history, match.home_team_id),
            away_win_rate_away=_form(away_history, match.away_team_id),
            h2h_home_win_rate=_h2h_win_rate(h2h_history, match.home_team_id),
            home_rest_days=_rest_days(home_recent, match.date),
            away_rest_days=_rest_days(away_recent, match.date),
        )
        rows.append({
            **features.__dict__,
            "home_score": match.home_score,
            "away_score": match.away_score,
            "result": _result(match),
            "date": match.date,
        })
    return pd.DataFrame(rows)
