import asyncio
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, Mock, call

import pytest

from discordbot.bot import Bot


@pytest.mark.asyncio
async def test_stop_closes_gateway_before_http_and_only_once() -> None:
    calls = Mock()
    ready = Mock()
    bot = cast(
        Bot,
        SimpleNamespace(
            _shutdown_lock=asyncio.Lock(),
            _shutdown_complete=False,
            _ready=ready,
            _connection_state=SimpleNamespace(stop=AsyncMock(wraps=calls.gateway_stop)),
            http=SimpleNamespace(close=AsyncMock(wraps=calls.http_close)),
        ),
    )

    await Bot.stop(bot)
    await Bot.stop(bot)

    assert calls.mock_calls == [call.gateway_stop(), call.http_close()]
    ready.clear.assert_called_once_with()
