import threading
from contextlib import nullcontext
from pathlib import Path
from typing import Any

import pytest

from decksite import database
from decksite.main import APP
from magic import database as magic_database
from shared.database import Database
from shared.pd_exception import DatabaseException


@pytest.mark.parametrize('request_context', [False, True])
@pytest.mark.parametrize('fails', [False, True])
def test_context_closes_connections_even_while_references_are_retained(request_context: bool, fails: bool) -> None:
    context = APP.test_request_context('/') if request_context else APP.app_context()
    with pytest.raises(RuntimeError, match='request failed') if fails else nullcontext():
        with context:
            decksite_db = database.db()
            cards_db = magic_database.db()
            assert decksite_db is database.db()
            assert cards_db is magic_database.db()
            assert decksite_db.value('SELECT 1') == cards_db.value('SELECT 1') == 1
            if fails:
                raise RuntimeError('request failed')

    # Retaining these objects (or an exception traceback) must not retain their
    # server connections until garbage collection or MySQL's idle timeout.
    assert not decksite_db.connection.open
    assert not cards_db.connection.open


def test_nested_app_contexts_have_independent_connection_lifetimes() -> None:
    with APP.app_context():
        outer = database.db()
        with APP.app_context():
            inner = database.db()
            assert inner is not outer
        assert not inner.connection.open
        assert outer.value('SELECT 1') == 1
    assert not outer.connection.open


def test_cards_connection_is_closed_when_decksite_cleanup_reports_an_open_transaction() -> None:
    with pytest.raises(DatabaseException, match='open transactions'):
        with APP.app_context():
            decksite_db = database.db()
            cards_db = magic_database.db()
            decksite_db.begin('uncommitted')

    assert not decksite_db.connection.open
    assert not cards_db.connection.open


def test_schema_initialization_releases_its_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    connections: list[Database] = []
    connect = database.get_database

    def track_connection(name: str) -> Database:
        connection = connect(name)
        connections.append(connection)
        return connection

    monkeypatch.setattr(database, 'get_database', track_connection)
    database.setup_in_app_context()

    assert connections
    assert all(not db.connection.open for db in connections)


def test_setup_serializes_migrations_and_rechecks_the_version(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class ConcurrentDatabase:
        def __init__(self) -> None:
            self.version = 0
            self.lock = threading.Lock()
            self.migration_started = threading.Event()
            self.finish_migration = threading.Event()
            self.second_checked_version = threading.Event()
            self.migration_calls: list[str] = []

        def get_lock(self, lock_id: str, timeout: int) -> None:
            assert lock_id == database.MIGRATION_LOCK
            assert timeout == database.MIGRATION_LOCK_TIMEOUT_SECONDS
            assert self.lock.acquire(timeout=timeout)

        def release_lock(self, lock_id: str) -> None:
            assert lock_id == database.MIGRATION_LOCK
            self.lock.release()

        def execute(self, sql: str, args: list[Any] | None = None) -> int:
            if sql == 'APPLY PATCH':
                self.migration_calls.append(threading.current_thread().name)
                self.migration_started.set()
                assert self.finish_migration.wait(timeout=5)
            elif sql.startswith('INSERT INTO db_version'):
                self.version = 1
            return 0

        def value(self, sql: str, args: list[Any], default: int) -> int:
            if threading.current_thread().name == 'second':
                self.second_checked_version.set()
            return self.version

    sql_dir = tmp_path / 'decksite' / 'sql'
    sql_dir.mkdir(parents=True)
    (sql_dir / '1.sql').write_text('APPLY PATCH;', encoding='utf-8')
    monkeypatch.chdir(tmp_path)
    fake_db = ConcurrentDatabase()
    monkeypatch.setattr(database, 'db', lambda: fake_db)
    errors: list[BaseException] = []

    def run_setup() -> None:
        try:
            database.setup()
        except BaseException as error:
            errors.append(error)

    first = threading.Thread(target=run_setup, name='first')
    second = threading.Thread(target=run_setup, name='second')
    first.start()
    assert fake_db.migration_started.wait(timeout=5)
    second.start()
    second_checked_version_while_patch_was_running = fake_db.second_checked_version.wait(timeout=0.25)
    fake_db.finish_migration.set()
    first.join(timeout=5)
    second.join(timeout=5)

    assert not first.is_alive()
    assert not second.is_alive()
    assert errors == []
    assert not second_checked_version_while_patch_was_running
    assert fake_db.migration_calls == ['first']
