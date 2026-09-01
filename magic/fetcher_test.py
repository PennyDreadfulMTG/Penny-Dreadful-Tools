from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock

import pytest

from magic import fetcher


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('helper', 'url'),
    [
        (fetcher.bugged_cards_async, 'https://pennydreadfulmtg.github.io/modo-bugs/bugs.json'),
        (fetcher.daybreak_forums_async, 'https://pennydreadfulmtg.github.io/modo-bugs/forums.json'),
    ],
)
async def test_modo_bug_helpers_fetch_asynchronously(
    monkeypatch: pytest.MonkeyPatch,
    helper: Callable[[], Awaitable[object]],
    url: str,
) -> None:
    fetch_json = AsyncMock(return_value={})
    monkeypatch.setattr(fetcher.fetch_tools, 'fetch_json_async', fetch_json)

    assert await helper() == {}
    fetch_json.assert_awaited_once_with(url)


@pytest.mark.asyncio
async def test_bulk_data_uri_uses_jsonl_download(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fetch_json_async(_url: str) -> dict:
        return {
            'data': [{
                'type': 'default_cards',
                'jsonl_download_uri': 'https://data.scryfall.io/default-cards.jsonl.gz',
            }],
        }

    monkeypatch.setattr(fetcher.fetch_tools, 'fetch_json_async', fetch_json_async)

    assert await fetcher.bulk_data_uri() == 'https://data.scryfall.io/default-cards.jsonl.gz'


@pytest.mark.asyncio
async def test_bulk_data_uri_supports_legacy_json_download(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fetch_json_async(_url: str) -> dict:
        return {
            'data': [{
                'type': 'default_cards',
                'download_uri': 'https://data.scryfall.io/default-cards.json',
            }],
        }

    monkeypatch.setattr(fetcher.fetch_tools, 'fetch_json_async', fetch_json_async)

    assert await fetcher.bulk_data_uri() == 'https://data.scryfall.io/default-cards.json'


def test_times_from_location_prefers_geographic_result(monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulates a query like "television" where the first result is a business (establishment)
    # and a later result is a geographic locality. The fix should skip the business result.
    geocode_response = {
        'results': [
            {
                'types': ['establishment', 'point_of_interest'],
                'formatted_address': 'Television, Some Business, CA',
                'geometry': {'location': {'lat': 10.0, 'lng': 20.0}},
            },
            {
                'types': ['locality', 'political'],
                'formatted_address': 'Television City, Los Angeles, CA, USA',
                'geometry': {'location': {'lat': 34.0, 'lng': -118.0}},
            },
        ],
    }
    timezone_response = {
        'status': 'OK',
        'timeZoneId': 'America/Los_Angeles',
    }

    monkeypatch.setattr(fetcher.configuration, 'get', lambda key: 'fake-key' if key == 'google_maps_api_key' else None)
    fetch_json_calls = iter([geocode_response, timezone_response])
    monkeypatch.setattr(fetcher.fetch_tools, 'fetch_json', lambda _url: next(fetch_json_calls))

    result = fetcher.times_from_location('television', False)
    addresses = list(result.values())[0]
    assert addresses == ['Television City, Los Angeles, CA, USA']


def test_times_from_location_falls_back_to_first_result_when_no_geographic(monkeypatch: pytest.MonkeyPatch) -> None:
    # When no result has a geographic type, fall back to results[0] as before.
    geocode_response = {
        'results': [
            {
                'types': ['establishment', 'point_of_interest'],
                'formatted_address': 'Some Business, CA',
                'geometry': {'location': {'lat': 10.0, 'lng': 20.0}},
            },
        ],
    }
    timezone_response = {
        'status': 'OK',
        'timeZoneId': 'America/Los_Angeles',
    }

    monkeypatch.setattr(fetcher.configuration, 'get', lambda key: 'fake-key' if key == 'google_maps_api_key' else None)
    fetch_json_calls = iter([geocode_response, timezone_response])
    monkeypatch.setattr(fetcher.fetch_tools, 'fetch_json', lambda _url: next(fetch_json_calls))

    result = fetcher.times_from_location('ninja', False)
    addresses = list(result.values())[0]
    assert addresses == ['Some Business, CA']
