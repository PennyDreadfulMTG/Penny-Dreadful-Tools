import asyncio
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, Mock, call

import pytest
from interactions import GLOBAL_SCOPE

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
            _get_sync_scopes=Mock(return_value=[GLOBAL_SCOPE]),
            application_commands=[SimpleNamespace(resolved_name='history', scopes=[GLOBAL_SCOPE])],
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
            _get_sync_scopes=Mock(return_value=[GLOBAL_SCOPE]),
            application_commands=[SimpleNamespace(resolved_name='history', scopes=[GLOBAL_SCOPE])],
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
            _get_sync_scopes=Mock(return_value=[GLOBAL_SCOPE]),
            application_commands=[SimpleNamespace(resolved_name='history', scopes=[GLOBAL_SCOPE])],
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
async def test_command_sync_does_not_require_group_roots_in_local_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    synchronise_interactions = AsyncMock()
    sleep = AsyncMock()
    exit_process = Mock()
    bot = cast(
        Bot,
        SimpleNamespace(
            sync_interactions=True,
            synchronise_interactions=synchronise_interactions,
            _get_sync_scopes=Mock(return_value=[GLOBAL_SCOPE]),
            application_commands=[
                SimpleNamespace(resolved_name='dreadrise', scopes=[GLOBAL_SCOPE]),
                SimpleNamespace(resolved_name='dreadrise search', scopes=[GLOBAL_SCOPE]),
            ],
            _interaction_lookup={'dreadrise search': Mock()},
        ),
    )
    monkeypatch.setattr('discordbot.bot.asyncio.sleep', sleep)
    monkeypatch.setattr('discordbot.bot.os._exit', exit_process)

    await Bot._init_interactions(bot)

    synchronise_interactions.assert_awaited_once_with()
    sleep.assert_not_awaited()
    exit_process.assert_not_called()


@pytest.mark.asyncio
async def test_command_sync_does_not_require_commands_outside_synced_scopes(monkeypatch: pytest.MonkeyPatch) -> None:
    synchronise_interactions = AsyncMock()
    sleep = AsyncMock()
    exit_process = Mock()
    bot = cast(
        Bot,
        SimpleNamespace(
            sync_interactions=True,
            synchronise_interactions=synchronise_interactions,
            _get_sync_scopes=Mock(return_value=[GLOBAL_SCOPE]),
            application_commands=[
                SimpleNamespace(resolved_name='history', scopes=[GLOBAL_SCOPE]),
                SimpleNamespace(resolved_name='queue join', scopes=[123]),
                SimpleNamespace(resolved_name='queue leave', scopes=[123]),
                SimpleNamespace(resolved_name='sync', scopes=[456]),
            ],
            _interaction_lookup={'history': Mock()},
        ),
    )
    monkeypatch.setattr('discordbot.bot.asyncio.sleep', sleep)
    monkeypatch.setattr('discordbot.bot.os._exit', exit_process)

    await Bot._init_interactions(bot)

    synchronise_interactions.assert_awaited_once_with()
    sleep.assert_not_awaited()
    exit_process.assert_not_called()


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
