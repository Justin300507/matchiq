import time

import requests

BASE_URL = "https://v3.football.api-sports.io"
CHAMPIONS_LEAGUE_ID = 2
MAX_RETRIES = 3
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def fetch_fixtures(api_key: str, league_id: int, season: int) -> dict:
    for attempt in range(MAX_RETRIES):
        response = requests.get(
            f"{BASE_URL}/fixtures",
            headers={"x-apisports-key": api_key},
            params={"league": league_id, "season": season},
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
