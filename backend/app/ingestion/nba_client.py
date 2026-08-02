import time

import requests

BASE_URL = "https://api.balldontlie.io/v1/games"
MAX_RETRIES = 3
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def fetch_games(api_key: str, start_date: str, end_date: str, cursor: int | None = None) -> dict:
    params = {"start_date": start_date, "end_date": end_date, "per_page": 100}
    if cursor is not None:
        params["cursor"] = cursor

    for attempt in range(MAX_RETRIES):
        response = requests.get(BASE_URL, headers={"Authorization": api_key}, params=params, timeout=30)
        try:
            response.raise_for_status()
            return response.json()
        except requests.HTTPError:
            status = response.status_code
            if status not in _RETRYABLE_STATUS_CODES or attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2 ** attempt)

    raise RuntimeError("unreachable")
