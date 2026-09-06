from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, Mock

import pytest

from magic import fetcher


def test_times_from_location_skips_business_results(monkeypatch: pytest.MonkeyPatch) -> None:
    geocode_response = {
        'results': [
            {
                'formatted_address': 'Ninja, 42 Business Road, London, UK',
                'geometry': {'location': {'lat': 51.0, 'lng': -0.1}},
                'types': ['establishment', 'point_of_interest'],
            },
            {
                'formatted_address': 'London, UK',
                'geometry': {'location': {'lat': 51.5, 'lng': -0.12}},
                'types': ['locality', 'political'],
            },
        ],
    }
    timezone_response = {'status': 'OK', 'timeZoneId': 'Europe/London'}
    fetch_json = Mock(side_effect=[geocode_response, timezone_response])
    monkeypatch.setattr(fetcher.configuration.google_maps_api_key, 'get', lambda: 'api-key')
    monkeypatch.setattr(fetcher.fetch_tools, 'fetch_json', fetch_json)
    monkeypatch.setattr(fetcher, 'current_time', lambda _timezone, _twentyfour: '12:34 PM')

    assert fetcher.times_from_location('ninja', False) == {'12:34 PM': ['London, UK']}
    assert 'location=51.5,-0.12' in fetch_json.call_args_list[1].args[0]


def test_times_from_location_rejects_only_business_results(monkeypatch: pytest.MonkeyPatch) -> None:
    fetch_json = Mock(return_value={
        'results': [{
            'formatted_address': 'Television Centre, London, UK',
            'geometry': {'location': {'lat': 51.0, 'lng': -0.1}},
            'types': ['establishment', 'point_of_interest'],
        }],
    })
    monkeypatch.setattr(fetcher.configuration.google_maps_api_key, 'get', lambda: 'api-key')
    monkeypatch.setattr(fetcher.fetch_tools, 'fetch_json', fetch_json)

    with pytest.raises(fetcher.TooFewItemsException):
        fetcher.times_from_location('television', False)
    fetch_json.assert_called_once()


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


@pytest.mark.asyncio
async def test_oracle_cards_uri_uses_oracle_bulk_file(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fetch_json_async(_url: str) -> dict:
        return {
            'data': [{
                'type': 'oracle_cards',
                'jsonl_download_uri': 'https://data.scryfall.io/oracle-cards.jsonl.gz',
            }],
        }

    monkeypatch.setattr(fetcher.fetch_tools, 'fetch_json_async', fetch_json_async)

    assert await fetcher.oracle_cards_uri() == 'https://data.scryfall.io/oracle-cards.jsonl.gz'
