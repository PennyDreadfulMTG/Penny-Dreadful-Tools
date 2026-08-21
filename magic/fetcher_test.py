import pytest

from magic import fetcher


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
