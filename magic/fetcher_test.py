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


@pytest.mark.parametrize('alias', ['EST', 'EDT', 'CST', 'CDT', 'MST', 'MDT', 'PST', 'PDT'])
def test_canonical_tz_aliases_always_include_expected_zone(alias: str) -> None:
    # Regardless of the current time of year, common US abbreviations must resolve
    # to their canonical IANA zone even when the clock has shifted to DST/standard.
    canonical = fetcher.CANONICAL_TZ_ALIASES[alias]
    results = fetcher.times_from_timezone_code(alias, twentyfour=True)
    all_zones = [zone for zones in results.values() for zone in zones]
    assert canonical in all_zones, f'{alias} did not include {canonical}; got {all_zones}'


def test_est_includes_new_york() -> None:
    # Regression test for #11645: /time EST was returning Jamaica but not New York.
    results = fetcher.times_from_timezone_code('EST', twentyfour=True)
    all_zones = [zone for zones in results.values() for zone in zones]
    assert 'America/New_York' in all_zones
