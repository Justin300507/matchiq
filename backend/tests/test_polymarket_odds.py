import json
from datetime import datetime
from unittest.mock import patch

from app.integrations.polymarket_odds import find_match_odds


def _market(question: str, yes_price: float) -> dict:
    return {
        "question": question,
        "outcomes": json.dumps(["Yes", "No"]),
        "outcomePrices": json.dumps([str(yes_price), str(round(1 - yes_price, 3))]),
    }


def _core_event(home: str, away: str, end_date: str, closed: bool = False) -> dict:
    return {
        "title": f"{home} vs. {away}",
        "slug": f"{home.lower().replace(' ', '-')}-vs-{away.lower().replace(' ', '-')}",
        "endDate": end_date,
        "closed": closed,
        "markets": [
            _market(f"Will {home} win on 2026-08-15?", 0.4),
            _market(f"Will {home} vs. {away} end in a draw?", 0.34),
            _market(f"Will {away} win on 2026-08-15?", 0.27),
        ],
    }


def _sub_market_event(home: str, away: str, end_date: str) -> dict:
    return {
        "title": f"{home} vs. {away} - Halftime Result",
        "slug": "irrelevant",
        "endDate": end_date,
        "closed": False,
        "markets": [_market(f"{home} leading at halftime?", 0.5)],
    }


@patch("app.integrations.polymarket_odds.search_events")
def test_find_match_odds_extracts_home_draw_away_from_a_real_shaped_event(mock_search):
    mock_search.return_value = [_core_event("Deportivo Alaves", "Getafe CF", "2026-08-15T20:00:00Z")]

    result = find_match_odds("Deportivo Alaves", "Getafe CF", datetime(2026, 8, 15, 20, 0))

    assert result is not None
    assert result.source == "Polymarket"
    assert result.home_decimal_odds == round(1 / 0.4, 3)
    assert result.draw_decimal_odds == round(1 / 0.34, 3)
    assert result.away_decimal_odds == round(1 / 0.27, 3)
    assert result.event_url.startswith("https://polymarket.com/event/")


@patch("app.integrations.polymarket_odds.search_events")
def test_find_match_odds_returns_none_when_nothing_found(mock_search):
    mock_search.return_value = []

    assert find_match_odds("Arsenal", "Chelsea", datetime(2026, 8, 21)) is None


@patch("app.integrations.polymarket_odds.search_events")
def test_find_match_odds_ignores_closed_events(mock_search):
    mock_search.return_value = [_core_event("Arsenal", "Chelsea", "2026-08-21T15:00:00Z", closed=True)]

    assert find_match_odds("Arsenal", "Chelsea", datetime(2026, 8, 21, 15, 0)) is None


@patch("app.integrations.polymarket_odds.search_events")
def test_find_match_odds_ignores_events_with_a_mismatched_date(mock_search):
    # Same two teams, but a fixture from months earlier -- not this match.
    mock_search.return_value = [_core_event("Arsenal", "Chelsea", "2025-01-10T15:00:00Z")]

    assert find_match_odds("Arsenal", "Chelsea", datetime(2026, 8, 21, 15, 0)) is None


@patch("app.integrations.polymarket_odds.search_events")
def test_find_match_odds_ignores_sibling_sub_market_events(mock_search):
    # Only a "- Halftime Result" sibling event exists, no core match event.
    mock_search.return_value = [_sub_market_event("Arsenal", "Chelsea", "2026-08-21T15:00:00Z")]

    assert find_match_odds("Arsenal", "Chelsea", datetime(2026, 8, 21, 15, 0)) is None


@patch("app.integrations.polymarket_odds.search_events")
def test_find_match_odds_matches_teams_regardless_of_home_away_order_in_title(mock_search):
    # Polymarket's title order doesn't necessarily match MatchIQ's home/away.
    mock_search.return_value = [_core_event("Chelsea", "Arsenal", "2026-08-21T15:00:00Z")]

    result = find_match_odds("Arsenal", "Chelsea", datetime(2026, 8, 21, 15, 0))

    assert result is not None
