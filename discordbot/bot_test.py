import asyncio
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, Mock, call

import pytest

from discordbot.bot import COMMAND_SYNC_ATTEMPTS, Bot


@pytest.mark.asyncio
async def test_command_sync_retries_before_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    synchronise_interactions = AsyncMock(side_effect=[RuntimeError('Discord unavailable'), None])
    sleep = AsyncMock()
    exit_process = Mock()
    bot = cast(
        Bot,
        SimpleNamespace(
            sync_interactions=True,
            synchronise_interactions=synchronise_interactions,
            application_commands=[SimpleNamespace(resolved_name='history')],
            _interaction_lookup={'history': Mock()},
        ),
    )
    monkeypatch.setattr('discordbot.bot.asyncio.sleep', sleep)
    monkeypatch.setattr('discordbot.bot.os._exit', exit_process)

    await Bot._init_interactions(bot)

    assert synchronise_interactions.await_count == 2
    sleep.assert_awaited_once_with(5)
    exit_process.assert_not_called()


@pytest.mark.asyncio
async def test_command_sync_exits_after_retries_are_exhausted(monkeypatch: pytest.MonkeyPatch) -> None:
    synchronise_interactions = AsyncMock(side_effect=RuntimeError('Discord unavailable'))
    sleep = AsyncMock()
    exit_process = Mock()
    bot = cast(
        Bot,
        SimpleNamespace(
            sync_interactions=True,
            synchronise_interactions=synchronise_interactions,
            application_commands=[SimpleNamespace(resolved_name='history')],
            _interaction_lookup={},
        ),
    )
    monkeypatch.setattr('discordbot.bot.asyncio.sleep', sleep)
    monkeypatch.setattr('discordbot.bot.os._exit', exit_process)

    await Bot._init_interactions(bot)

    assert synchronise_interactions.await_count == COMMAND_SYNC_ATTEMPTS
    assert [call.args[0] for call in sleep.await_args_list] == [5, 10]
    exit_process.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_command_sync_retries_when_local_cache_is_incomplete(monkeypatch: pytest.MonkeyPatch) -> None:
    synchronise_interactions = AsyncMock()
    bot = cast(
        Bot,
        SimpleNamespace(
            sync_interactions=True,
            synchronise_interactions=synchronise_interactions,
            application_commands=[SimpleNamespace(resolved_name='history')],
            _interaction_lookup={},
        ),
    )
    monkeypatch.setattr('discordbot.bot.asyncio.sleep', AsyncMock())
    exit_process = Mock()
    monkeypatch.setattr('discordbot.bot.os._exit', exit_process)

    await Bot._init_interactions(bot)

    assert synchronise_interactions.await_count == COMMAND_SYNC_ATTEMPTS
    exit_process.assert_called_once_with(1)


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
