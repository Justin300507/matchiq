import json
from dataclasses import dataclass
from datetime import datetime

from app.integrations.polymarket_client import search_events

# Polymarket creates a match's markets close to kickoff, and only for a
# subset of leagues/fixtures -- most calls to find_match_odds() will
# legitimately find nothing. That's not a bug; there's genuinely no
# Polymarket market for most matches MatchIQ tracks.
_DATE_TOLERANCE_DAYS = 4


@dataclass
class MarketOdds:
    source: str
    event_title: str
    event_url: str
    home_decimal_odds: float
    draw_decimal_odds: float | None
    away_decimal_odds: float


def _names_match(name: str, candidate: str) -> bool:
    name, candidate = name.lower(), candidate.lower()
    return name in candidate or candidate in name


def _is_core_match_event(title: str) -> bool:
    """Polymarket also creates sibling events for the same fixture
    ('<home> vs. <away> - Halftime Result', '... - Exact Score', etc.) --
    the one we want is titled exactly '<home> vs. <away>'."""
    if " vs. " not in title:
        return False
    _, away_part = title.split(" vs. ", 1)
    return " - " not in away_part


def _event_matches_teams(event: dict, home_team: str, away_team: str) -> bool:
    title = event.get("title", "")
    if not _is_core_match_event(title):
        return False
    home_part, away_part = title.split(" vs. ", 1)
    return (_names_match(home_team, home_part) and _names_match(away_team, away_part)) or (
        _names_match(home_team, away_part) and _names_match(away_team, home_part)
    )


def _event_matches_date(event: dict, match_date: datetime) -> bool:
    # Polymarket's event-level "startDate" is when the *market* opened for
    # trading (often weeks before kickoff) -- the actual kickoff time is
    # "endDate", confirmed against real events (e.g. a market whose
    # startDate was 2026-08-02 but endDate was the real 2026-08-15 kickoff).
    end_date_str = event.get("endDate")
    if not end_date_str:
        return False
    try:
        event_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return False
    return abs((event_date - match_date).days) <= _DATE_TOLERANCE_DAYS


def _probability_from_market(market: dict) -> float | None:
    try:
        outcomes = json.loads(market.get("outcomes", "[]"))
        prices = json.loads(market.get("outcomePrices", "[]"))
    except (json.JSONDecodeError, TypeError):
        return None
    for outcome, price in zip(outcomes, prices):
        if outcome == "Yes":
            try:
                return float(price)
            except (TypeError, ValueError):
                return None
    return None


def _decimal_odds_from_prob(prob: float | None) -> float | None:
    if prob is None or prob <= 0:
        return None
    return round(1 / prob, 3)


def find_match_odds(home_team: str, away_team: str, match_date: datetime) -> MarketOdds | None:
    """Looks for a live Polymarket market for this exact match, matched by
    team names and kickoff date. Returns None whenever nothing genuinely
    matches -- never a guessed or partial result."""
    events = search_events(f"{home_team} vs {away_team}")
    candidates = [
        event
        for event in events
        if not event.get("closed")
        and _event_matches_teams(event, home_team, away_team)
        and _event_matches_date(event, match_date)
    ]
    if not candidates:
        return None
    event = candidates[0]

    home_prob = draw_prob = away_prob = None
    for market in event.get("markets", []):
        question = market.get("question", "")
        prob = _probability_from_market(market)
        if prob is None:
            continue
        if "draw" in question.lower():
            draw_prob = prob
        elif _names_match(home_team, question):
            home_prob = prob
        elif _names_match(away_team, question):
            away_prob = prob

    home_odds = _decimal_odds_from_prob(home_prob)
    away_odds = _decimal_odds_from_prob(away_prob)
    if home_odds is None or away_odds is None:
        return None

    return MarketOdds(
        source="Polymarket",
        event_title=event.get("title", ""),
        event_url=f"https://polymarket.com/event/{event.get('slug', '')}",
        home_decimal_odds=home_odds,
        draw_decimal_odds=_decimal_odds_from_prob(draw_prob),
        away_decimal_odds=away_odds,
    )
