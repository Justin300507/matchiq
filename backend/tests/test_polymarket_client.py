from unittest.mock import patch

from app.integrations.polymarket_client import search_events


@patch("app.integrations.polymarket_client.requests.get")
def test_search_events_queries_the_public_search_endpoint(mock_get):
    mock_get.return_value.json.return_value = {"events": [{"id": "1", "title": "Arsenal vs. Chelsea"}]}
    mock_get.return_value.raise_for_status.return_value = None

    result = search_events("Arsenal vs Chelsea")

    assert result == [{"id": "1", "title": "Arsenal vs. Chelsea"}]
    called_url = mock_get.call_args.args[0]
    called_params = mock_get.call_args.kwargs["params"]
    assert called_url.endswith("/public-search")
    assert called_params["q"] == "Arsenal vs Chelsea"


@patch("app.integrations.polymarket_client.requests.get")
def test_search_events_returns_empty_list_when_no_events_key(mock_get):
    mock_get.return_value.json.return_value = {}
    mock_get.return_value.raise_for_status.return_value = None

    assert search_events("nonexistent teams") == []
