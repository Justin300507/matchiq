from unittest.mock import patch

import requests

from app.ingestion.api_football_client import CHAMPIONS_LEAGUE_ID, fetch_fixtures


@patch("app.ingestion.api_football_client.requests.get")
def test_fetch_fixtures_sends_auth_header_and_params(mock_get):
    mock_get.return_value.json.return_value = {"response": [{"fixture": {"id": 1}}]}
    mock_get.return_value.raise_for_status.return_value = None

    result = fetch_fixtures(api_key="secret", league_id=CHAMPIONS_LEAGUE_ID, season=2026)

    assert result["response"] == [{"fixture": {"id": 1}}]
    called_url = mock_get.call_args.args[0]
    called_headers = mock_get.call_args.kwargs["headers"]
    called_params = mock_get.call_args.kwargs["params"]
    assert called_url.endswith("/fixtures")
    assert called_headers["x-apisports-key"] == "secret"
    assert called_params["league"] == CHAMPIONS_LEAGUE_ID
    assert called_params["season"] == 2026


@patch("app.ingestion.api_football_client.time.sleep")
@patch("app.ingestion.api_football_client.requests.get")
def test_fetch_fixtures_retries_on_rate_limit_then_succeeds(mock_get, mock_sleep):
    rate_limited = requests.Response()
    rate_limited.status_code = 429

    def raise_rate_limited():
        raise requests.HTTPError(response=rate_limited)

    rate_limited.raise_for_status = raise_rate_limited

    ok_response = requests.Response()
    ok_response.status_code = 200
    ok_response.json = lambda: {"response": []}
    ok_response.raise_for_status = lambda: None

    mock_get.side_effect = [rate_limited, ok_response]

    result = fetch_fixtures(api_key="secret", league_id=CHAMPIONS_LEAGUE_ID, season=2026)

    assert result == {"response": []}
    assert mock_get.call_count == 2
    assert mock_sleep.call_count == 1


@patch("app.ingestion.api_football_client.time.sleep")
@patch("app.ingestion.api_football_client.requests.get")
def test_fetch_fixtures_raises_after_max_retries(mock_get, mock_sleep):
    failing = requests.Response()
    failing.status_code = 503

    def raise_error():
        raise requests.HTTPError(response=failing)

    failing.raise_for_status = raise_error
    mock_get.return_value = failing

    try:
        fetch_fixtures(api_key="secret", league_id=CHAMPIONS_LEAGUE_ID, season=2026)
        assert False, "expected HTTPError"
    except requests.HTTPError:
        pass

    assert mock_get.call_count == 3
