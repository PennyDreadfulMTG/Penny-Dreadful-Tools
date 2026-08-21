from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, Mock

import pytest

from discordbot import error_handling, reboot_utils
from discordbot.background import BackgroundTasks


@pytest.mark.asyncio
async def test_successful_reboot_records_channel_for_next_start(monkeypatch: pytest.MonkeyPatch) -> None:
    bot = SimpleNamespace(stop=AsyncMock())
    background = SimpleNamespace(
        bot=bot,
        do_reboot_key=reboot_utils.REBOOT_KEY,
        send_reboot_message=AsyncMock(),
    )
    monkeypatch.setattr(reboot_utils, 'update', AsyncMock(return_value=None))
    monkeypatch.setattr('discordbot.background.redis_wrapper.get_bool', Mock(return_value=True))
    monkeypatch.setattr('discordbot.background.redis_wrapper.get_int', Mock(return_value=123))
    clear = Mock()
    store = Mock()
    monkeypatch.setattr('discordbot.background.redis_wrapper.clear', clear)
    monkeypatch.setattr('discordbot.background.redis_wrapper.store', store)
    exit_process = Mock()
    monkeypatch.setattr('discordbot.background.os._exit', exit_process)
    await BackgroundTasks.background_task_reboot.callback(background)

    store.assert_called_once_with(reboot_utils.REBOOT_COMPLETE_CHANNEL_KEY, 123, ex=3600)
    bot.stop.assert_awaited_once()
    exit_process.assert_called_once_with(0)
    background.send_reboot_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_successful_reboot_forces_exit_after_shutdown_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    bot = SimpleNamespace(stop=AsyncMock(side_effect=TimeoutError))
    background = SimpleNamespace(
        bot=bot,
        do_reboot_key=reboot_utils.REBOOT_KEY,
        send_reboot_message=AsyncMock(),
    )
    monkeypatch.setattr(reboot_utils, 'update', AsyncMock(return_value=None))
    monkeypatch.setattr('discordbot.background.redis_wrapper.get_bool', Mock(return_value=True))
    monkeypatch.setattr('discordbot.background.redis_wrapper.get_int', Mock(return_value=123))
    monkeypatch.setattr('discordbot.background.redis_wrapper.clear', Mock())
    monkeypatch.setattr('discordbot.background.redis_wrapper.store', Mock())
    exit_process = Mock()
    monkeypatch.setattr('discordbot.background.os._exit', exit_process)

    await BackgroundTasks.background_task_reboot.callback(background)

    exit_process.assert_called_once_with(0)


@pytest.mark.asyncio
async def test_failed_reboot_sends_short_public_error(monkeypatch: pytest.MonkeyPatch) -> None:
    failure = reboot_utils.RebootUpdateError('git pull', 1, 'many\nlines\nof technical output')
    bot = SimpleNamespace(stop=AsyncMock())
    background = SimpleNamespace(
        bot=bot,
        do_reboot_key=reboot_utils.REBOOT_KEY,
        send_reboot_message=AsyncMock(),
    )
    monkeypatch.setattr(reboot_utils, 'update', AsyncMock(return_value=failure))
    monkeypatch.setattr('discordbot.background.redis_wrapper.get_bool', Mock(return_value=True))
    monkeypatch.setattr('discordbot.background.redis_wrapper.get_int', Mock(return_value=123))
    monkeypatch.setattr('discordbot.background.redis_wrapper.clear', Mock())

    await BackgroundTasks.background_task_reboot.callback(background)

    message = background.send_reboot_message.await_args.args[1]
    assert '\n' not in message
    assert len(message) <= error_handling.MAX_PUBLIC_ERROR_LENGTH
    assert 'many' not in message
    assert 'RebootUpdateError: git pull exited with status' in message
    bot.stop.assert_not_awaited()


@pytest.mark.asyncio
async def test_startup_announces_completed_reboot(monkeypatch: pytest.MonkeyPatch) -> None:
    send_reboot_message = AsyncMock()
    background = cast(
        BackgroundTasks,
        SimpleNamespace(
            bot=SimpleNamespace(commit_id='1234567890abcdef'),
            send_reboot_message=send_reboot_message,
        ),
    )
    monkeypatch.setattr('discordbot.background.redis_wrapper.get_int', Mock(return_value=123))
    clear = Mock()
    monkeypatch.setattr('discordbot.background.redis_wrapper.clear', clear)

    await BackgroundTasks.announce_reboot_complete(background)

    clear.assert_called_once_with(reboot_utils.REBOOT_COMPLETE_CHANNEL_KEY)
    send_reboot_message.assert_awaited_once_with(123, 'Reboot complete. Loaded `12345678`')
