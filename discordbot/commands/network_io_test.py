from collections import defaultdict
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from discordbot.commands import art, downtimes, modobug, mos_league, randomcard, randomdeck, resources, rhinos, rulings, scry, status, welcome, whois
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


@pytest.mark.asyncio
async def test_status_defers_before_fetching(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = SimpleNamespace(defer=AsyncMock(), send=AsyncMock())

    async def fetch_status() -> str:
        ctx.defer.assert_awaited_once_with()
        return 'UP'

    monkeypatch.setattr(status.fetcher, 'mtgo_status', fetch_status)

    await status.Status.status.callback(SimpleNamespace(), ctx)

    ctx.send.assert_awaited_once_with('MTGO is UP')


@pytest.mark.asyncio
async def test_whois_mtgo_defers_before_fetching(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = SimpleNamespace(defer=AsyncMock(), send=AsyncMock())

    async def fetch_person(_username: str) -> str:
        ctx.defer.assert_awaited_once_with()
        return 'found'

    monkeypatch.setattr(whois, 'whois_mtgo', fetch_person)

    await whois.Whois.whois_mtgo.callback(SimpleNamespace(), ctx, 'tester')

    ctx.send.assert_awaited_once_with('found')


@pytest.mark.asyncio
async def test_whois_discord_defers_before_fetching(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = SimpleNamespace(defer=AsyncMock(), send=AsyncMock())
    user = SimpleNamespace(id=123, mention='<@123>')

    async def fetch_person(_user: object) -> str:
        ctx.defer.assert_awaited_once_with()
        return 'found'

    monkeypatch.setattr(whois, 'whois_discord', fetch_person)

    await whois.Whois.whois_discord.callback(SimpleNamespace(), ctx, user)

    ctx.send.assert_awaited_once_with('found')


@pytest.mark.asyncio
async def test_art_defers_before_downloading(monkeypatch: pytest.MonkeyPatch) -> None:
    card = SimpleNamespace(name='Island')
    ctx = SimpleNamespace(author=SimpleNamespace(mention='<@123>'), defer=AsyncMock(), send=AsyncMock(), send_image_with_retry=AsyncMock())

    async def download(_card: object, _path: str, version: str) -> bool:
        ctx.defer.assert_awaited_once_with()
        assert version == 'art_crop'
        return True

    monkeypatch.setattr(art.image_fetcher, 'determine_filepath', Mock(return_value='/tmp/island.jpg'))
    monkeypatch.setattr(art.image_fetcher, 'download_scryfall_card_image', download)

    await art.Art.art.callback(SimpleNamespace(), ctx, card)

    ctx.send_image_with_retry.assert_awaited_once_with('/tmp/island.art_crop.jpg')


@pytest.mark.asyncio
@pytest.mark.parametrize(('callback_name', 'card_name'), [('welcome', 'Welcome to the Fold'), ('back_for_more', 'Back for More')])
async def test_greetings_defer_before_downloading(
    monkeypatch: pytest.MonkeyPatch,
    callback_name: str,
    card_name: str,
) -> None:
    card = SimpleNamespace(name=card_name)
    ctx = SimpleNamespace(defer=AsyncMock())

    async def greeting(_ctx: object, sent_card: object, *args: object) -> None:
        ctx.defer.assert_awaited_once_with()
        assert sent_card is card

    monkeypatch.setattr(welcome.oracle, 'cards_by_name', Mock(return_value={card_name: card}))
    monkeypatch.setattr(welcome, 'greeting', greeting)

    callback = getattr(welcome.Welcome, callback_name).callback
    await callback(SimpleNamespace(), ctx)


@pytest.mark.asyncio
async def test_random_card_defers_before_posting(monkeypatch: pytest.MonkeyPatch) -> None:
    card = SimpleNamespace(name='Island')
    ctx = SimpleNamespace(defer=AsyncMock(), post_cards=AsyncMock())

    async def post_cards(*_args: object) -> None:
        ctx.defer.assert_awaited_once_with()

    ctx.post_cards.side_effect = post_cards
    monkeypatch.setattr(randomcard.oracle, 'legal_cards', Mock(return_value=['Island']))
    monkeypatch.setattr(randomcard.oracle, 'cards_by_name', Mock(return_value={'Island': card}))

    await randomcard.RandomCard.randomcard.callback(SimpleNamespace(), ctx, 1)

    ctx.post_cards.assert_awaited_once_with([card], None, '')


@pytest.mark.asyncio
async def test_mos_queue_defers_before_fetching_league(monkeypatch: pytest.MonkeyPatch) -> None:
    channel_id = 456
    ctx = SimpleNamespace(channel_id=channel_id, author_id=123, defer=AsyncMock(), send=AsyncMock())

    async def get_current_league() -> None:
        ctx.defer.assert_awaited_once_with(ephemeral=True)
        return None

    monkeypatch.setattr(mos_league.configuration, 'get_int', Mock(return_value=channel_id))
    monkeypatch.setattr(mos_league, 'get_current_league', get_current_league)
    extension = SimpleNamespace(queues=defaultdict(list))

    await mos_league.MosLeague.queue_join.callback(extension, ctx)

    ctx.send.assert_awaited_once_with('The league is currently closed', ephemeral=True)


@pytest.mark.asyncio
async def test_modo_bug_triage_defers_before_fetching(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = SimpleNamespace(defer=AsyncMock(), send=AsyncMock())

    async def fetch_bugs() -> list[object]:
        ctx.defer.assert_awaited_once_with()
        return []

    monkeypatch.setattr(modobug.fetcher, 'bugged_cards_async', fetch_bugs)
    monkeypatch.setattr(modobug.fetcher, 'daybreak_forums_async', AsyncMock(return_value={}))

    await modobug.ModoBugs.triage.callback(SimpleNamespace(), ctx)

    ctx.send.assert_awaited_once_with(embeds=[])


@pytest.mark.asyncio
async def test_modo_bug_queue_moves_github_update_off_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    bug = {
        'card': 'Island',
        'description': 'Broken',
        'issue_number': 123,
        'support_thread': None,
        'url': 'https://example.com/bug',
    }
    post = {
        'status': 'Confirmed',
        'title': 'Island is broken',
        'tracked': False,
        'url': 'https://example.com/thread',
    }
    message = SimpleNamespace(edit=AsyncMock())
    ctx = SimpleNamespace(defer=AsyncMock(), send=AsyncMock(return_value=message))

    async def wait_for_component(_message: object, *, components: list[object], timeout: object) -> object:
        assert timeout is None
        return SimpleNamespace(ctx=SimpleNamespace(custom_id=getattr(components[0], 'custom_id')))

    extension = SimpleNamespace(bot=SimpleNamespace(wait_for_component=wait_for_component), blacklist=set())
    monkeypatch.setattr(modobug.fetcher, 'bugged_cards_async', AsyncMock(return_value=[bug]))
    monkeypatch.setattr(modobug.fetcher, 'daybreak_forums_async', AsyncMock(return_value={'thread': post}))
    to_thread = AsyncMock()
    monkeypatch.setattr(modobug.asyncio, 'to_thread', to_thread)

    await modobug.ModoBugs.queue.callback(extension, ctx)

    ctx.defer.assert_awaited_once_with()
    to_thread.assert_awaited_once_with(modobug.associate_thread, bug, post)
