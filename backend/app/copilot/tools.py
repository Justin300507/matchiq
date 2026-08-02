from datetime import datetime, timezone

import requests
from sqlalchemy.orm import Session

from app.copilot.lookups import find_team_by_name, find_upcoming_match
from app.features.build_features import compute_features_bulk
from app.integrations.polymarket_odds import find_match_odds
from app.ml.explain import explain_prediction
from app.ml.predict import load_latest_artifact, predict_batch, predict_match
from app.ml.team_profile import compute_team_profile
from app.models_db import Match

_UPCOMING_LIMIT = 25


# Every tool below takes (db, artifact_dir, **kwargs) even when it doesn't
# need artifact_dir, so the engine's dispatch loop can call any tool the
# same way without per-tool special-casing.


def get_upcoming_predictions(db: Session, artifact_dir, *, sport: str, league: str | None = None) -> str:
    artifact = load_latest_artifact(sport, artifact_dir)
    if artifact is None:
        return f"No trained prediction model is currently available for sport={sport}."

    query = db.query(Match).filter(
        Match.sport == sport,
        Match.status == "scheduled",
        Match.date >= datetime.now(timezone.utc).replace(tzinfo=None),
    )
    if league is not None:
        query = query.filter(Match.league == league)
    matches = query.order_by(Match.date.asc()).limit(_UPCOMING_LIMIT).all()
    if not matches:
        scope = f"sport={sport}" + (f", league={league}" if league else "")
        return f"There are no upcoming matches currently loaded for {scope}."

    features_by_id = compute_features_bulk(db, sport, matches)
    predictions = predict_batch(artifact, [features_by_id[match.id] for match in matches])
    lines = []
    for match, prediction in zip(matches, predictions):
        draw_part = f", draw_win_prob={prediction.draw_prob:.2f}" if prediction.draw_prob is not None else ""
        lines.append(
            f"- {match.date.isoformat()} | {match.league} | "
            f"{match.home_team.name} vs {match.away_team.name} | "
            f"home_win_prob={prediction.home_win_prob:.2f}{draw_part}, "
            f"away_win_prob={prediction.away_win_prob:.2f} | "
            f"predicted_score={prediction.predicted_home_score:.1f}-{prediction.predicted_away_score:.1f} | "
            f"confidence={prediction.confidence}"
        )
    return "\n".join(lines)


def get_team_profile(db: Session, artifact_dir, *, team_name: str, sport: str) -> str:
    team = find_team_by_name(db, team_name, sport)
    if team is None:
        return f"No team found matching '{team_name}' in sport={sport}."

    profile = compute_team_profile(db, team)
    return (
        f"{profile.team_name} ({profile.league}) — Elo rating: {profile.elo_rating:.0f}. "
        f"Record: {profile.wins}W-{profile.draws}D-{profile.losses}L over {profile.matches_played} matches. "
        f"Last 5 form: {profile.last5_form or 'n/a'}. "
        f"Goals for/against per match: {profile.goals_for_avg:.2f}/{profile.goals_against_avg:.2f}. "
        f"Home win rate: {profile.home_win_rate:.0%}, away win rate: {profile.away_win_rate:.0%}."
    )


def get_match_explanation(db: Session, artifact_dir, *, home_team: str, away_team: str, sport: str) -> str:
    match = find_upcoming_match(db, home_team, away_team, sport)
    if match is None:
        return f"No upcoming match found between '{home_team}' and '{away_team}' in sport={sport}."

    artifact = load_latest_artifact(sport, artifact_dir)
    if artifact is None:
        return f"No trained prediction model is currently available for sport={sport}."

    features = compute_features_bulk(db, sport, [match])[match.id]
    prediction = predict_match(artifact, features)
    explanation = explain_prediction(artifact, features)
    factor_lines = "\n".join(
        f"  - {factor.label}: {factor.relative_influence_pct:+.1f}% relative influence toward the home side"
        for factor in explanation.factors
    )
    draw_part = f", draw_prob={prediction.draw_prob:.2f}" if prediction.draw_prob is not None else ""
    return (
        f"{match.home_team.name} vs {match.away_team.name} ({match.league}, {match.date.isoformat()}):\n"
        f"home_win_prob={prediction.home_win_prob:.2f}{draw_part}, "
        f"away_win_prob={prediction.away_win_prob:.2f}, confidence={prediction.confidence}\n"
        f"Factors behind the prediction:\n{factor_lines}"
    )


def get_market_odds(db: Session, artifact_dir, *, home_team: str, away_team: str, sport: str) -> str:
    match = find_upcoming_match(db, home_team, away_team, sport)
    if match is None:
        return f"No upcoming match found between '{home_team}' and '{away_team}' in sport={sport}."

    try:
        odds = find_match_odds(match.home_team.name, match.away_team.name, match.date)
    except requests.exceptions.RequestException:
        return "Polymarket is temporarily unreachable -- no odds available right now."

    if odds is None:
        return f"No live Polymarket market found for {match.home_team.name} vs {match.away_team.name}."

    draw_part = f", draw_decimal_odds={odds.draw_decimal_odds}" if odds.draw_decimal_odds is not None else ""
    return (
        f"Polymarket odds for {match.home_team.name} vs {match.away_team.name}: "
        f"home_decimal_odds={odds.home_decimal_odds}{draw_part}, away_decimal_odds={odds.away_decimal_odds}. "
        f"Source: {odds.event_url}"
    )


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_upcoming_predictions",
            "description": "Get MatchIQ's real upcoming-match predictions for a sport, optionally filtered to one league.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sport": {"type": "string", "enum": ["nba", "football"]},
                    "league": {
                        "type": "string",
                        "description": "Optional league filter, e.g. 'EPL', 'La Liga'. Omit for all leagues in the sport.",
                    },
                },
                "required": ["sport"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_team_profile",
            "description": "Get a team's real record, Elo rating, recent form, and goal stats.",
            "parameters": {
                "type": "object",
                "properties": {
                    "team_name": {"type": "string"},
                    "sport": {"type": "string", "enum": ["nba", "football"]},
                },
                "required": ["team_name", "sport"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_match_explanation",
            "description": (
                "Get the real model prediction and the factors behind it for a specific upcoming "
                "match between two teams."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "home_team": {"type": "string"},
                    "away_team": {"type": "string"},
                    "sport": {"type": "string", "enum": ["nba", "football"]},
                },
                "required": ["home_team", "away_team", "sport"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_odds",
            "description": (
                "Get live Polymarket odds for a specific upcoming match between two teams, if a "
                "market exists for it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "home_team": {"type": "string"},
                    "away_team": {"type": "string"},
                    "sport": {"type": "string", "enum": ["nba", "football"]},
                },
                "required": ["home_team", "away_team", "sport"],
            },
        },
    },
]

TOOL_FUNCTIONS = {
    "get_upcoming_predictions": get_upcoming_predictions,
    "get_team_profile": get_team_profile,
    "get_match_explanation": get_match_explanation,
    "get_market_odds": get_market_odds,
}
