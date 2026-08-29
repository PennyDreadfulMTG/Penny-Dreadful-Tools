import asyncio
import datetime
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, Mock

import pytest

from discordbot import background as background_module
from discordbot import error_handling, reboot_utils
from discordbot.background import BackgroundTasks
from magic import fetcher


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


def stale_cards_background(scryfall: datetime.datetime, ours: list[datetime.datetime], run_command: AsyncMock, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    monkeypatch.setattr('discordbot.background.configuration.prevent_cards_db_updates', SimpleNamespace(get=lambda: False))
    monkeypatch.setattr('discordbot.background.os.path.exists', Mock(return_value=False))
    monkeypatch.setattr('discordbot.background.database.last_updated', Mock(side_effect=ours))
    monkeypatch.setattr('discordbot.background.fetcher.scryfall_last_updated_async', AsyncMock(return_value=scryfall))
    monkeypatch.setattr(reboot_utils, 'run_command', run_command)
    return SimpleNamespace(updating_cards=False)


@pytest.mark.asyncio
async def test_stale_cards_are_updated_out_of_process_and_reloaded(monkeypatch: pytest.MonkeyPatch) -> None:
    old, new = datetime.datetime(2026, 8, 23, tzinfo=datetime.UTC), datetime.datetime(2026, 8, 27, tzinfo=datetime.UTC)
    run_command = AsyncMock(return_value=(0, 'done'))
    background = stale_cards_background(new, [old, new, new], run_command, monkeypatch)
    oracle_init = Mock()
    monkeypatch.setattr('discordbot.background.oracle.init', oracle_init)
    searcher = Mock()
    monkeypatch.setattr('discordbot.background.command.searcher', Mock(return_value=searcher))

    await BackgroundTasks.background_task_update_cards.callback(background)

    run_command.assert_awaited_once_with(*background_module.UPDATE_CARDS_COMMAND)
    oracle_init.assert_called_once_with(force=True)
    searcher.refresh.assert_called_once_with()


@pytest.mark.asyncio
async def test_fresh_cards_are_left_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    ours = datetime.datetime(2026, 8, 27, tzinfo=datetime.UTC)
    run_command = AsyncMock()
    background = stale_cards_background(ours, [ours], run_command, monkeypatch)
    oracle_init = Mock()
    monkeypatch.setattr('discordbot.background.oracle.init', oracle_init)

    await BackgroundTasks.background_task_update_cards.callback(background)

    run_command.assert_not_awaited()
    oracle_init.assert_not_called()


@pytest.mark.asyncio
async def test_cards_are_not_reloaded_if_the_update_did_not_happen(monkeypatch: pytest.MonkeyPatch) -> None:
    old, new = datetime.datetime(2026, 8, 23, tzinfo=datetime.UTC), datetime.datetime(2026, 8, 27, tzinfo=datetime.UTC)
    run_command = AsyncMock(return_value=(1, 'Unable to connect to Scryfall.'))
    background = stale_cards_background(new, [old, old], run_command, monkeypatch)
    oracle_init = Mock()
    monkeypatch.setattr('discordbot.background.oracle.init', oracle_init)

    await BackgroundTasks.background_task_update_cards.callback(background)

    run_command.assert_awaited_once()
    oracle_init.assert_not_called()


@pytest.mark.asyncio
async def test_unreachable_scryfall_does_not_trigger_an_update(monkeypatch: pytest.MonkeyPatch) -> None:
    ours = datetime.datetime(2026, 8, 23, tzinfo=datetime.UTC)
    run_command = AsyncMock()
    background = stale_cards_background(ours, [ours], run_command, monkeypatch)
    monkeypatch.setattr('discordbot.background.fetcher.scryfall_last_updated_async', AsyncMock(side_effect=fetcher.FetchException('no')))

    await BackgroundTasks.background_task_update_cards.callback(background)

    run_command.assert_not_awaited()


@pytest.mark.asyncio
async def test_frozen_cards_db_is_not_updated(monkeypatch: pytest.MonkeyPatch) -> None:
    old, new = datetime.datetime(2026, 8, 23, tzinfo=datetime.UTC), datetime.datetime(2026, 8, 27, tzinfo=datetime.UTC)
    run_command = AsyncMock()
    background = stale_cards_background(new, [old], run_command, monkeypatch)
    monkeypatch.setattr('discordbot.background.configuration.prevent_cards_db_updates', SimpleNamespace(get=lambda: True))

    await BackgroundTasks.background_task_update_cards.callback(background)

    run_command.assert_not_awaited()


@pytest.mark.asyncio
async def test_cards_are_not_updated_during_rotation(monkeypatch: pytest.MonkeyPatch) -> None:
    old, new = datetime.datetime(2026, 8, 23, tzinfo=datetime.UTC), datetime.datetime(2026, 8, 27, tzinfo=datetime.UTC)
    run_command = AsyncMock()
    background = stale_cards_background(new, [old], run_command, monkeypatch)
    monkeypatch.setattr('discordbot.background.os.path.exists', Mock(return_value=True))

    await BackgroundTasks.background_task_update_cards.callback(background)

    run_command.assert_not_awaited()


def test_the_subprocess_we_shell_out_to_is_a_real_command() -> None:
    import run
    _, script, command = background_module.UPDATE_CARDS_COMMAND
    assert script == 'run.py'
    assert command in run.cli.commands


@pytest.mark.asyncio
async def test_a_second_tick_does_not_start_a_second_update(monkeypatch: pytest.MonkeyPatch) -> None:
    old, new = datetime.datetime(2026, 8, 23, tzinfo=datetime.UTC), datetime.datetime(2026, 8, 27, tzinfo=datetime.UTC)
    started, release, calls = asyncio.Event(), asyncio.Event(), 0

    async def run_command(*args: str) -> tuple[int, str]:
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        return 0, 'done'

    background = stale_cards_background(new, [old, new, new], cast(AsyncMock, run_command), monkeypatch)
    monkeypatch.setattr('discordbot.background.oracle.init', Mock())
    monkeypatch.setattr('discordbot.background.command.searcher', Mock(return_value=Mock()))

    first = asyncio.create_task(BackgroundTasks.background_task_update_cards.callback(background))
    await started.wait()
    await BackgroundTasks.background_task_update_cards.callback(background)  # The next tick, while the first is still going.
    release.set()
    await first

    assert calls == 1
    assert background.updating_cards is False
