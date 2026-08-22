from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from discordbot.commands import spoiler
from shared.fetch_tools import FetchException


@pytest.mark.asyncio
async def test_spoiler_does_not_send_invalid_image(monkeypatch: pytest.MonkeyPatch) -> None:
    card = {
        'object': 'card',
        'name': 'Unnatural Summons',
        'set': 'ydsk',
        'collector_number': '27',
        'mana_cost': '{1}{G}{U}',
        'image_uris': {'normal': 'https://example.com/not-an-image.jpg'},
    }
    ctx = SimpleNamespace(
        author=SimpleNamespace(mention='<@123>'),
        bot=Mock(),
        send=AsyncMock(),
    )
    monkeypatch.setattr(spoiler.fetch_tools, 'fetch_json', Mock(return_value=card))
    monkeypatch.setattr(spoiler.fetch_tools, 'store_image', Mock(side_effect=FetchException('invalid image')))
    monkeypatch.setattr(spoiler.configuration, 'get', Mock(return_value='/tmp'))
    monkeypatch.setattr(spoiler.emoji, 'replace_emoji', AsyncMock(return_value='Unnatural Summons 1GU'))
    import_card = AsyncMock()
    monkeypatch.setattr(spoiler.oracle, 'scryfall_import_async', import_card)

    await spoiler.Spoiler.spoiler.callback(SimpleNamespace(), ctx, 'Unnatural Summons')

    ctx.send.assert_awaited_once_with(content='Unnatural Summons 1GU\nImage unavailable.')
    import_card.assert_awaited_once_with('Unnatural Summons')
