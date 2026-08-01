from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.models_db import Match, Team

_TERMINAL_NON_PLAYABLE = {"postponed", "cancelled", "suspended", "awarded"}


@dataclass
class RawGame:
    external_id: str
    sport: str
    league: str
    date: datetime
    home_team_external_id: str
    home_team_name: str
    away_team_external_id: str
    away_team_name: str
    home_score: int | None
    away_score: int | None
    status: str


def _normalize_status(raw_status: str) -> str:
    normalized = raw_status.strip().lower()
    if normalized in ("final", "finished"):
        return "final"
    if normalized in _TERMINAL_NON_PLAYABLE:
        return "other"
    return "scheduled"


def normalize_nba_game(raw: dict) -> RawGame:
    return RawGame(
        external_id=str(raw["id"]),
        sport="nba",
        league="NBA",
        date=datetime.fromisoformat(raw["date"].replace("Z", "+00:00")),
        home_team_external_id=str(raw["home_team"]["id"]),
        home_team_name=raw["home_team"]["full_name"],
        away_team_external_id=str(raw["visitor_team"]["id"]),
        away_team_name=raw["visitor_team"]["full_name"],
        home_score=raw["home_team_score"],
        away_score=raw["visitor_team_score"],
        status=_normalize_status(raw["status"]),
    )


def normalize_soccer_game(raw: dict, league: str) -> RawGame:
    full_time = raw["score"]["fullTime"]
    return RawGame(
        external_id=str(raw["id"]),
        sport="soccer",
        league=league,
        date=datetime.fromisoformat(raw["utcDate"].replace("Z", "+00:00")),
        home_team_external_id=str(raw["homeTeam"]["id"]),
        home_team_name=raw["homeTeam"]["name"],
        away_team_external_id=str(raw["awayTeam"]["id"]),
        away_team_name=raw["awayTeam"]["name"],
        home_score=full_time["home"],
        away_score=full_time["away"],
        status=_normalize_status(raw["status"]),
    )


_API_FOOTBALL_FINAL_STATUSES = {"ft", "aet", "pen"}
_API_FOOTBALL_NON_PLAYABLE_STATUSES = {"pst", "canc", "abd", "awd", "wo"}


def _normalize_api_football_status(status_short: str) -> str:
    normalized = status_short.strip().lower()
    if normalized in _API_FOOTBALL_FINAL_STATUSES:
        return "final"
    if normalized in _API_FOOTBALL_NON_PLAYABLE_STATUSES:
        return "other"
    return "scheduled"


def normalize_api_football_fixture(raw: dict) -> RawGame:
    # Prefixed IDs keep this provider's numbering from colliding with
    # football-data.org's, since both are plain integers sharing the
    # same (sport, external_id) uniqueness constraint.
    fixture = raw["fixture"]
    teams = raw["teams"]
    goals = raw["goals"]
    return RawGame(
        external_id=f"af-{fixture['id']}",
        sport="soccer",
        league="Champions League",
        date=datetime.fromisoformat(fixture["date"]),
        home_team_external_id=f"af-{teams['home']['id']}",
        home_team_name=teams["home"]["name"],
        away_team_external_id=f"af-{teams['away']['id']}",
        away_team_name=teams["away"]["name"],
        home_score=goals["home"],
        away_score=goals["away"],
        status=_normalize_api_football_status(fixture["status"]["short"]),
    )


def _get_or_create_team(db: Session, sport: str, league: str, external_id: str, name: str) -> Team:
    team = (
        db.query(Team)
        .filter(Team.sport == sport, Team.external_id == external_id)
        .one_or_none()
    )
    if team is None:
        team = Team(external_id=external_id, sport=sport, league=league, name=name)
        db.add(team)
        db.flush()
    return team


def upsert_game(db: Session, game: RawGame) -> Match:
    home = _get_or_create_team(db, game.sport, game.league, game.home_team_external_id, game.home_team_name)
    away = _get_or_create_team(db, game.sport, game.league, game.away_team_external_id, game.away_team_name)

    match = (
        db.query(Match)
        .filter(Match.sport == game.sport, Match.external_id == game.external_id)
        .one_or_none()
    )
    if match is None:
        match = Match(
            external_id=game.external_id,
            sport=game.sport,
            league=game.league,
            date=game.date,
            home_team_id=home.id,
            away_team_id=away.id,
            home_score=game.home_score,
            away_score=game.away_score,
            status=game.status,
        )
        db.add(match)
    else:
        match.home_score = game.home_score
        match.away_score = game.away_score
        match.status = game.status
    db.commit()
    return match
