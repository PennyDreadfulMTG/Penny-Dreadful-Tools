from unittest.mock import AsyncMock, Mock

import pytest

from discordbot.commands.explain import ExplainCog


@pytest.mark.asyncio
async def test_explain_showchat() -> None:
    ctx = Mock()
    ctx.send = AsyncMock()

    await ExplainCog.explain.callback(None, ctx, 'showchat')

    ctx.send.assert_awaited_once_with(
        'If game chat is hidden on Magic Online, click the chat icon in the bottom-left corner of the game window, then select `Show Chat`.',
    )
