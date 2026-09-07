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
