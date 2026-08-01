import time

import requests

BASE_URL = "https://api.football-data.org/v4"
MAX_RETRIES = 3
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

LEAGUE_CODES = {
    "EPL": "PL",
    "La Liga": "PD",
    "Serie A": "SA",
    "Bundesliga": "BL1",
    "Ligue 1": "FL1",
}


def fetch_matches(api_key: str, league: str, season: int) -> dict:
    if league not in LEAGUE_CODES:
        raise ValueError(f"Unknown league: {league}")

    code = LEAGUE_CODES[league]
    url = f"{BASE_URL}/competitions/{code}/matches"

    for attempt in range(MAX_RETRIES):
        response = requests.get(
            url,
            headers={"X-Auth-Token": api_key},
            params={"season": season},
            timeout=30,
        )
        try:
            response.raise_for_status()
            return response.json()
        except requests.HTTPError:
            status = response.status_code
            if status not in _RETRYABLE_STATUS_CODES or attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2 ** attempt)

    raise RuntimeError("unreachable")
