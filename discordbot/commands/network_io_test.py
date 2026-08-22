from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from discordbot.commands import downtimes, randomdeck, resources, rhinos, rulings, scry
from discordbot.commands import time as time_command


@pytest.mark.asyncio
async def test_random_deck_defers_and_fetches_asynchronously(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = SimpleNamespace(author=SimpleNamespace(mention='<@123>'), defer=AsyncMock(), send=AsyncMock())
    fetch_json = AsyncMock(return_value={'error': True, 'msg': 'offline'})
    monkeypatch.setattr(randomdeck.fetcher, 'decksite_url', Mock(return_value='https://example.com/api/randomlegaldeck'))
    monkeypatch.setattr(randomdeck.fetch_tools, 'fetch_json_async', fetch_json)

    await randomdeck.RandomDeck.randomdeck.callback(SimpleNamespace(), ctx)

    ctx.defer.assert_awaited_once_with()
    fetch_json.assert_awaited_once_with('https://example.com/api/randomlegaldeck')


@pytest.mark.asyncio
async def test_downtimes_defers_and_fetches_asynchronously(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = SimpleNamespace(defer=AsyncMock(), send=AsyncMock())
    fetch = AsyncMock(return_value='No scheduled downtime.')
    monkeypatch.setattr(downtimes.fetch_tools, 'fetch_async', fetch)

    await downtimes.Downtimes.downtimes.callback(SimpleNamespace(), ctx)

    ctx.defer.assert_awaited_once_with()
    fetch.assert_awaited_once_with('https://pennydreadfulmtg.github.io/modo-bugs/downtimes.txt')
    ctx.send.assert_awaited_once_with('No scheduled downtime.')


@pytest.mark.asyncio
async def test_scry_moves_legacy_search_off_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = SimpleNamespace(author=SimpleNamespace(), post_cards=AsyncMock())
    to_thread = AsyncMock(return_value=(0, [], []))
    monkeypatch.setattr(scry.asyncio, 'to_thread', to_thread)
    monkeypatch.setattr(scry.oracle, 'cards_by_name', Mock(return_value={}))

    await scry.Scry.scry.callback(SimpleNamespace(), ctx, 'f:pd')

    to_thread.assert_awaited_once_with(scry.fetcher.search_scryfall, 'f:pd')
    ctx.post_cards.assert_awaited_once_with([], ctx.author, '')


@pytest.mark.asyncio
async def test_resources_moves_sitemap_fetch_off_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = SimpleNamespace(author=SimpleNamespace(mention='<@123>'), send=AsyncMock())
    to_thread = AsyncMock(return_value={})
    monkeypatch.setattr(resources.asyncio, 'to_thread', to_thread)
    monkeypatch.setattr(resources, 'resources_resources', Mock(return_value={}))

    await resources.Resources.resources.callback(SimpleNamespace(), ctx, 'cards bolt')

    to_thread.assert_awaited_once_with(resources.site_resources, 'cards bolt')


@pytest.mark.asyncio
async def test_time_defers_and_moves_location_fetch_off_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = SimpleNamespace(
        author=SimpleNamespace(mention='<@123>'),
        channel=SimpleNamespace(id=456),
        defer=AsyncMock(),
        send=AsyncMock(),
    )
    to_thread = AsyncMock(return_value={'12:00': ['America/New_York']})
    monkeypatch.setattr(time_command.asyncio, 'to_thread', to_thread)
    monkeypatch.setattr(time_command, 'guild_id', Mock(return_value=123))
    monkeypatch.setattr(time_command, 'with_config_file', Mock(side_effect=lambda _id: nullcontext()))
    monkeypatch.setattr(time_command.configuration, 'use_24h', SimpleNamespace(value=True))

    await time_command.Time.time.callback(SimpleNamespace(), ctx, 'New York')

    ctx.defer.assert_awaited_once_with()
    to_thread.assert_awaited_once_with(time_command.fetcher.time, 'New York', True)
    ctx.send.assert_awaited_once_with('New York: 12:00\n')


@pytest.mark.asyncio
async def test_rulings_moves_scryfall_fetch_off_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    card = SimpleNamespace(name='Lightning Bolt')
    ctx = SimpleNamespace(single_card_text=AsyncMock())
    raw_rulings = [{'comment': 'Lightning Bolt deals 3 damage.'}]
    to_thread = AsyncMock(return_value=raw_rulings)
    monkeypatch.setattr(rulings.asyncio, 'to_thread', to_thread)

    await rulings.Rulings.rulings.callback(SimpleNamespace(), ctx, card)

    to_thread.assert_awaited_once_with(rulings.fetcher.rulings, 'Lightning Bolt')
    sent_card, formatter = ctx.single_card_text.await_args.args
    assert sent_card is card
    assert formatter(card) == 'Lightning Bolt deals 3 damage.'


@pytest.mark.asyncio
async def test_rhinos_defers_and_moves_searches_off_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    cards = {
        'Siege Rhino': SimpleNamespace(name='Siege Rhino'),
        'Copy Rhino': SimpleNamespace(name='Copy Rhino'),
        'Zombie Rhino': SimpleNamespace(name='Zombie Rhino'),
        'Tutor Rhino': SimpleNamespace(name='Tutor Rhino'),
    }
    ctx = SimpleNamespace(defer=AsyncMock(), post_cards=AsyncMock())
    to_thread = AsyncMock(side_effect=[cards['Copy Rhino'], cards['Zombie Rhino'], cards['Tutor Rhino']])
    monkeypatch.setattr(rhinos.random, 'random', Mock(return_value=1))
    monkeypatch.setattr(rhinos.oracle, 'cards_by_name', Mock(return_value=cards))
    monkeypatch.setattr(rhinos.asyncio, 'to_thread', to_thread)

    await rhinos.Rhinos.rhinos.callback(SimpleNamespace(), ctx)

    ctx.defer.assert_awaited_once_with()
    assert to_thread.await_count == 3
    assert all(call.args[0].__name__ == 'find_rhino' for call in to_thread.await_args_list)
