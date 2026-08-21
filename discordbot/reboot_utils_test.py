from unittest.mock import AsyncMock

import pytest

from discordbot import error_handling, reboot_utils


@pytest.mark.asyncio
async def test_update_runs_pull_then_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    run_command = AsyncMock(side_effect=[(0, 'pulled'), (0, 'synced')])
    monkeypatch.setattr(reboot_utils, '_run_command', run_command)

    assert await reboot_utils.update() is None
    assert run_command.await_count == 2
    assert run_command.await_args_list[0].args == ('git', 'pull')
    assert run_command.await_args_list[1].args == ('uv', 'sync', '--frozen')


@pytest.mark.asyncio
async def test_update_reports_pull_failure_and_does_not_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    run_command = AsyncMock(return_value=(1, 'fatal: pull failed'))
    monkeypatch.setattr(reboot_utils, '_run_command', run_command)

    failure = await reboot_utils.update()

    assert isinstance(failure, reboot_utils.RebootUpdateError)
    assert str(failure) == 'git pull exited with status 1'
    assert failure.output == 'fatal: pull failed'
    message = error_handling.public_message(failure)
    assert '\n' not in message
    assert len(message) <= 200
    assert 'fatal: pull failed' not in message
    assert 'RebootUpdateError: git pull exited with status 1' in message
    run_command.assert_awaited_once_with('git', 'pull')


@pytest.mark.asyncio
async def test_update_reports_sync_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    run_command = AsyncMock(side_effect=[(0, 'pulled'), (2, 'sync failed')])
    monkeypatch.setattr(reboot_utils, '_run_command', run_command)

    failure = await reboot_utils.update()

    assert isinstance(failure, reboot_utils.RebootUpdateError)
    assert str(failure) == 'uv sync exited with status 2'
    assert failure.output == 'sync failed'


def test_public_message_redacts_secrets_and_url_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(error_handling.repo, 'REDACTED_STRINGS', {'secret'})
    failure = reboot_utils.RebootUpdateError('git pull', 1, 'details')

    message = error_handling.public_message(failure, 'secret https://username:password@example.com/repo')

    assert 'secret' not in message
    assert 'username:password' not in message
    assert 'REDACTED' in message
