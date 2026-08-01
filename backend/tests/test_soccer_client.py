from unittest.mock import patch

import requests

from app.ingestion.soccer_client import LEAGUE_CODES, fetch_matches


def test_league_codes_cover_top_5_leagues():
    assert LEAGUE_CODES == {
        "EPL": "PL",
        "La Liga": "PD",
        "Serie A": "SA",
        "Bundesliga": "BL1",
        "Ligue 1": "FL1",
    }


@patch("app.ingestion.soccer_client.requests.get")
def test_fetch_matches_sends_auth_header_and_season(mock_get):
    mock_get.return_value.json.return_value = {"matches": [{"id": 1}]}
    mock_get.return_value.raise_for_status.return_value = None

    result = fetch_matches(api_key="secret", league="EPL", season=2025)

    assert result["matches"] == [{"id": 1}]
    called_url = mock_get.call_args.args[0]
    called_headers = mock_get.call_args.kwargs["headers"]
    called_params = mock_get.call_args.kwargs["params"]
    assert called_url.endswith("/competitions/PL/matches")
    assert called_headers["X-Auth-Token"] == "secret"
    assert called_params["season"] == 2025


def test_fetch_matches_rejects_unknown_league():
    try:
        fetch_matches(api_key="secret", league="Not A League", season=2025)
        assert False, "expected ValueError"
    except ValueError:
        pass


@patch("app.ingestion.soccer_client.time.sleep")
@patch("app.ingestion.soccer_client.requests.get")
def test_fetch_matches_retries_on_rate_limit_then_succeeds(mock_get, mock_sleep):
    rate_limited = requests.Response()
    rate_limited.status_code = 429

    def raise_rate_limited():
        raise requests.HTTPError(response=rate_limited)

    rate_limited.raise_for_status = raise_rate_limited

    ok_response = requests.Response()
    ok_response.status_code = 200
    ok_response.json = lambda: {"matches": []}
    ok_response.raise_for_status = lambda: None

    mock_get.side_effect = [rate_limited, ok_response]

    result = fetch_matches(api_key="secret", league="EPL", season=2025)

    assert result == {"matches": []}
    assert mock_get.call_count == 2
    assert mock_sleep.call_count == 1


@patch("app.ingestion.soccer_client.time.sleep")
@patch("app.ingestion.soccer_client.requests.get")
def test_fetch_matches_raises_after_max_retries(mock_get, mock_sleep):
    failing = requests.Response()
    failing.status_code = 503

    def raise_error():
        raise requests.HTTPError(response=failing)

    failing.raise_for_status = raise_error
    mock_get.return_value = failing

    try:
        fetch_matches(api_key="secret", league="EPL", season=2025)
        assert False, "expected HTTPError"
    except requests.HTTPError:
        pass

    assert mock_get.call_count == 3
