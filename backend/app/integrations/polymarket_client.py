import time

import requests

# Polymarket's Gamma API is public and unauthenticated -- no key required
# for read-only market data. https://gamma-api.polymarket.com
BASE_URL = "https://gamma-api.polymarket.com"
MAX_RETRIES = 3
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def search_events(query: str) -> list[dict]:
    """Free-text search across Polymarket events (e.g. two team names).
    Returns whatever events Polymarket indexes for that query -- most
    matches will return nothing, since Polymarket only creates per-match
    markets for a subset of leagues/fixtures, not comprehensive coverage."""
    params = {"q": query}

    for attempt in range(MAX_RETRIES):
        response = requests.get(f"{BASE_URL}/public-search", params=params, timeout=15)
        try:
            response.raise_for_status()
            return response.json().get("events", [])
        except requests.HTTPError:
            status = response.status_code
            if status not in _RETRYABLE_STATUS_CODES or attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2**attempt)

    raise RuntimeError("unreachable")
