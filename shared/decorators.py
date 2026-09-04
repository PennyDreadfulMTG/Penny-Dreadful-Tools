import functools
import logging
import pathlib
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from typing import cast

from flask import has_request_context

from shared import configuration
from shared.database import get_database
from shared.pd_exception import DatabaseException, LockNotAcquiredException

logger = logging.getLogger(__name__)

_REPRIME_COOLDOWN_SECONDS = 5 * 60
_last_reprime_schedule: float | None = None
_reprime_schedule_lock = threading.Lock()


def empty_dict[K, V]() -> dict[K, V]:
    return {}


def empty_list[T]() -> list[T]:
    return []


def empty_optional[T]() -> T | None:
    return None


def empty_page[T]() -> tuple[list[T], int]:
    return [], 0


def schedule_reprime_cache() -> None:
    """Start a detached reprime in production, at most once per worker per cooldown period.

    The task runner's system-wide, non-blocking lock ensures that processes spawned by different
    web workers or hosts cannot actually run concurrently.
    """
    if not configuration.production.value:
        return

    global _last_reprime_schedule
    with _reprime_schedule_lock:
        now = time.monotonic()
        if _last_reprime_schedule is not None and now - _last_reprime_schedule < _REPRIME_COOLDOWN_SECONDS:
            return
        root = pathlib.Path(__file__).resolve().parent.parent
        python = pathlib.Path(sys.prefix) / 'bin' / 'python'
        try:
            subprocess.Popen(
                [str(python), str(root / 'run.py'), 'maintenance', 'reprime_cache'],
                cwd=root,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError:
            logger.exception('Unable to schedule reprime_cache in the background.')
            return
        _last_reprime_schedule = now
        logger.warning('Scheduled reprime_cache in the background after a database read failed.')


class _RetryAfterCalling:
    def __init__(self, retry_func: Callable[[], None], fallback: Callable[[], object]) -> None:
        self.retry_func = retry_func
        self.fallback = fallback

    def __call__[**P, T](self, decorated_func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(decorated_func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                return decorated_func(*args, **kwargs)
            except DatabaseException as e:
                if has_request_context():  # type: ignore
                    logger.error(f"Got {e} trying to call {decorated_func.__name__}. Returning its fallback during a web request.")
                    schedule_reprime_cache()
                    return cast(T, self.fallback())
                logger.error(f"Got {e} trying to call {decorated_func.__name__} outside a web request, so calling {self.retry_func.__name__} first.")
                self.retry_func()
                try:
                    return decorated_func(*args, **kwargs)
                except DatabaseException:
                    logger.error("That didn't help, giving up.")
                    raise
        return wrapper


def retry_after_calling(retry_func: Callable[[], None], *, fallback: Callable[[], object]) -> _RetryAfterCalling:
    """Retry failed database reads outside HTTP requests; return declared empty data within them.

    Requiring every caller to declare a typed fallback makes a new preaggregate-backed loader fail
    during development if its no-data behavior has not been considered explicitly.
    """
    return _RetryAfterCalling(retry_func, fallback)


def lock[T](func: Callable[..., T]) -> T:
    return func()


class _SystemwideLock:
    def __init__(self, lock_key: str) -> None:
        self.lock_key = lock_key

    def __call__[**P](self, f: Callable[P, None]) -> Callable[P, None]:
        @functools.wraps(f)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
            lock_db = get_database(configuration.get_str('decksite_database'))
            acquired = False
            try:
                try:
                    lock_db.get_lock(self.lock_key, 0)
                    acquired = True
                except LockNotAcquiredException:
                    logger.warning(f'Not running {f.__name__} because system-wide lock {self.lock_key} is already held.')
                    return
                return f(*args, **kwargs)
            finally:
                try:
                    if acquired:
                        lock_db.release_lock(self.lock_key)
                finally:
                    lock_db.close()
        return wrapper


def interprocess_locked(path: str) -> _SystemwideLock:
    """Allow only one system-wide run, without queueing duplicate invocations.

    MySQL named locks are shared by every process and host using the same production database,
    unlike the old checkout-relative file lock. They are also released if a process exits.
    """
    return _SystemwideLock(f'penny-dreadful-tools:{path}')
