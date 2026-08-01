from unittest.mock import patch

import requests

from app.ingestion.nba_client import fetch_games


@patch("app.ingestion.nba_client.requests.get")
def test_fetch_games_sends_auth_header_and_date_range(mock_get):
    mock_get.return_value.json.return_value = {
        "data": [{"id": 1}],
        "meta": {"next_cursor": None},
    }
    mock_get.return_value.raise_for_status.return_value = None

    result = fetch_games(api_key="secret", start_date="2026-01-01", end_date="2026-01-02")

    assert result["data"] == [{"id": 1}]
    called_url = mock_get.call_args.args[0]
    called_headers = mock_get.call_args.kwargs["headers"]
    called_params = mock_get.call_args.kwargs["params"]
    assert "balldontlie.io" in called_url
    assert called_headers["Authorization"] == "secret"
    assert called_params["start_date"] == "2026-01-01"
    assert called_params["end_date"] == "2026-01-02"


@patch("app.ingestion.nba_client.requests.get")
def test_fetch_games_passes_cursor_when_given(mock_get):
    mock_get.return_value.json.return_value = {"data": [], "meta": {"next_cursor": None}}
    mock_get.return_value.raise_for_status.return_value = None

    fetch_games(api_key="secret", start_date="2026-01-01", end_date="2026-01-02", cursor=42)

    called_params = mock_get.call_args.kwargs["params"]
    assert called_params["cursor"] == 42


@patch("app.ingestion.nba_client.time.sleep")
@patch("app.ingestion.nba_client.requests.get")
def test_fetch_games_retries_on_rate_limit_then_succeeds(mock_get, mock_sleep):
    rate_limited = requests.Response()
    rate_limited.status_code = 429
    ok_response = requests.Response()
    ok_response.status_code = 200
    ok_response.json = lambda: {"data": [], "meta": {"next_cursor": None}}

    def raise_for_rate_limited():
        raise requests.HTTPError(response=rate_limited)

    rate_limited.raise_for_status = raise_for_rate_limited
    ok_response.raise_for_status = lambda: None

    mock_get.side_effect = [rate_limited, ok_response]

    result = fetch_games(api_key="secret", start_date="2026-01-01", end_date="2026-01-02")

    assert result == {"data": [], "meta": {"next_cursor": None}}
    assert mock_get.call_count == 2
    assert mock_sleep.call_count == 1


@patch("app.ingestion.nba_client.time.sleep")
@patch("app.ingestion.nba_client.requests.get")
def test_fetch_games_raises_after_max_retries(mock_get, mock_sleep):
    failing = requests.Response()
    failing.status_code = 500

    def raise_error():
        raise requests.HTTPError(response=failing)

    failing.raise_for_status = raise_error
    mock_get.return_value = failing

    try:
        fetch_games(api_key="secret", start_date="2026-01-01", end_date="2026-01-02")
        assert False, "expected HTTPError"
    except requests.HTTPError:
        pass

    assert mock_get.call_count == 3
