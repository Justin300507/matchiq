from datetime import datetime, timezone

import anthropic
from sqlalchemy.orm import Session

from app.features.build_features import compute_features
from app.ml.predict import load_latest_artifact, predict_match
from app.models_db import Match

_MODEL = "claude-opus-5"
_CONTEXT_MATCH_LIMIT = 25

# The analyst can only ever see what MatchIQ actually has: real upcoming
# matches and the trained model's own predictions. It's told explicitly not
# to fabricate injury/weather/lineup/odds data, since none of that exists
# in the system.
_SYSTEM_PROMPT = (
    "You are MatchIQ's built-in analyst. Answer the user's question using ONLY "
    "the upcoming-match prediction data provided in this message — it is the "
    "complete, real dataset MatchIQ currently has loaded for this sport/league. "
    "MatchIQ has no injury, weather, lineup, possession, xG, or betting-odds "
    "data. If the question needs any of that, say plainly that MatchIQ doesn't "
    "have it rather than guessing or inventing an answer. Be concise, and cite "
    "specific teams, probabilities, predicted scores, and confidence levels "
    "from the data when they're relevant to the answer."
)


def _build_match_context(db: Session, artifact_dir, sport: str, league: str | None) -> str:
    artifact = load_latest_artifact(sport, artifact_dir)
    if artifact is None:
        return "No trained prediction model is currently available for this sport."

    query = db.query(Match).filter(
        Match.sport == sport,
        Match.status == "scheduled",
        Match.date >= datetime.now(timezone.utc).replace(tzinfo=None),
    )
    if league is not None:
        query = query.filter(Match.league == league)

    matches = query.order_by(Match.date.asc()).limit(_CONTEXT_MATCH_LIMIT).all()
    if not matches:
        return "There are no upcoming matches currently loaded for this sport/league."

    lines = []
    for match in matches:
        features = compute_features(db, match)
        prediction = predict_match(artifact, features)
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


def answer_question(
    db: Session,
    artifact_dir,
    sport: str,
    league: str | None,
    question: str,
    api_key: str,
) -> str:
    context = _build_match_context(db, artifact_dir, sport, league)
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=_MODEL,
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Upcoming match predictions:\n{context}\n\nQuestion: {question}",
            }
        ],
    )
    return next(block.text for block in response.content if block.type == "text")
