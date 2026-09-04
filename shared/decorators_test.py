import pathlib
import subprocess
import sys
from unittest import mock
from uuid import uuid4

import pytest
from flask import Flask

from shared import configuration, decorators
from shared.database import get_database
from shared.pd_exception import DatabaseException, LockNotAcquiredException


def named_mock(name: str, **kwargs: object) -> mock.Mock:
    result = mock.Mock(**kwargs)
    result.__name__ = name
    return result


def test_retry_after_calling_requires_the_developer_to_choose_a_fallback() -> None:
    retry = named_mock('retry')

    with pytest.raises(TypeError, match='fallback'):
        decorators.retry_after_calling(retry)  # type: ignore[call-arg]


def test_retry_after_calling_retries_outside_a_web_request() -> None:
    retry = named_mock('retry')
    decorated = named_mock('decorated', side_effect=[DatabaseException('missing'), 'ok'])
    wrapped = decorators.retry_after_calling(retry, fallback=list)(decorated)

    assert wrapped() == 'ok'
    retry.assert_called_once_with()


def test_retry_after_calling_returns_fallback_and_schedules_reprime_during_a_web_request(monkeypatch: pytest.MonkeyPatch) -> None:
    app = Flask(__name__)
    retry = named_mock('retry')
    fallback = mock.Mock(return_value=['empty'])
    schedule = mock.Mock()
    monkeypatch.setattr(decorators, 'schedule_reprime_cache', schedule)

    @decorators.retry_after_calling(retry, fallback=fallback)
    def unavailable() -> list[str]:
        raise DatabaseException('missing')

    with app.test_request_context('/'):
        assert unavailable() == ['empty']

    retry.assert_not_called()
    fallback.assert_called_once_with()
    schedule.assert_called_once_with()


def test_schedule_reprime_cache_is_production_only(monkeypatch: pytest.MonkeyPatch) -> None:
    popen = mock.Mock()
    monkeypatch.setitem(configuration.CONFIG, 'production', False)
    monkeypatch.setattr(decorators.subprocess, 'Popen', popen)

    decorators.schedule_reprime_cache()

    popen.assert_not_called()


def test_schedule_reprime_cache_detaches_once_per_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    popen = mock.Mock()
    monkeypatch.setitem(configuration.CONFIG, 'production', True)
    monkeypatch.setattr(decorators.subprocess, 'Popen', popen)
    monkeypatch.setattr(decorators.time, 'monotonic', lambda: 42.0)
    monkeypatch.setattr(decorators, '_last_reprime_schedule', None)

    decorators.schedule_reprime_cache()
    decorators.schedule_reprime_cache()

    root = pathlib.Path(decorators.__file__).resolve().parent.parent
    python = pathlib.Path(sys.prefix) / 'bin' / 'python'
    popen.assert_called_once_with(
        [str(python), str(root / 'run.py'), 'maintenance', 'reprime_cache'],
        cwd=root,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )


def test_interprocess_locked_uses_a_nonblocking_systemwide_database_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    lock_db = mock.Mock()
    monkeypatch.setattr(decorators, 'get_database', mock.Mock(return_value=lock_db))
    work = mock.Mock(return_value=None)
    work.__name__ = 'work'

    wrapped = decorators.interprocess_locked('.task.lock')(work)

    assert wrapped() is None
    work.assert_called_once_with()
    lock_db.get_lock.assert_called_once_with('penny-dreadful-tools:.task.lock', 0)
    lock_db.release_lock.assert_called_once_with('penny-dreadful-tools:.task.lock')
    lock_db.close.assert_called_once_with()


def test_interprocess_locked_does_not_queue_another_run(monkeypatch: pytest.MonkeyPatch) -> None:
    lock_db = mock.Mock()
    lock_db.get_lock.side_effect = LockNotAcquiredException
    monkeypatch.setattr(decorators, 'get_database', mock.Mock(return_value=lock_db))
    work = mock.Mock()
    work.__name__ = 'work'

    wrapped = decorators.interprocess_locked('.task.lock')(work)

    assert wrapped() is None
    work.assert_not_called()
    lock_db.release_lock.assert_not_called()
    lock_db.close.assert_called_once_with()


@pytest.mark.functional
def test_interprocess_locked_contends_across_real_database_connections() -> None:
    path = f'.test-{uuid4()}.lock'
    lock_key = f'penny-dreadful-tools:{path}'
    holder = get_database(configuration.get_str('decksite_database'))
    calls: list[bool] = []

    @decorators.interprocess_locked(path)
    def work() -> None:
        calls.append(True)

    holder.get_lock(lock_key, 0)
    try:
        work()
        assert calls == []
    finally:
        holder.release_lock(lock_key)
        holder.close()

    work()
    assert calls == [True]
