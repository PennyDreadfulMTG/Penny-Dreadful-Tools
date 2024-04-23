import warnings
from collections.abc import Iterable
from typing import Any, cast

import MySQLdb
from MySQLdb import OperationalError

from shared import configuration, perf
from shared.pd_exception import (DatabaseConnectionRefusedException, DatabaseException,
                                 DatabaseMissingException, InvalidArgumentException,
                                 LockNotAcquiredException)

ValidSqlArgumentDescription = Any

class Database():
    def __init__(self, db: str) -> None:
        warnings.filterwarnings('error', category=MySQLdb.Warning)
        self.name = db
        self.host = configuration.mysql_host.value
        self.port = configuration.mysql_port.value
        self.user = configuration.mysql_user.value
        self.passwd = configuration.mysql_passwd.value
        self.open_transactions: list[str] = []
        self.connect()

    def connect(self) -> None:
        try:
            self.connection = MySQLdb.connect(host=self.host, port=self.port, user=self.user, passwd=self.passwd, use_unicode=True, charset='utf8', autocommit=True)
            self.cursor = self.connection.cursor(MySQLdb.cursors.DictCursor)
            self.execute('SET NAMES utf8mb4')
            try:
                self.execute(f'USE {self.name}')
            except DatabaseException:
                print(f'Creating database {self.name}')
                self.execute(f'CREATE DATABASE {self.name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
                self.execute(f'USE {self.name}')
        except MySQLdb.Error as c:
            msg = f'Failed to initialize database in `{self.name}`'
            if c.args[0] in [2002, 2003]:
                raise DatabaseConnectionRefusedException(msg) from c
            raise DatabaseException(msg) from c

    def select(self, sql: str, args: list[ValidSqlArgumentDescription] | None = None) -> list[dict[str, ValidSqlArgumentDescription]]:
        [_, rows] = self.execute_anything(sql, args)
        return rows

    def execute(self, sql: str, args: list[ValidSqlArgumentDescription] | None = None) -> int:
        [n, _] = self.execute_anything(sql, args, False)
        return n

    def execute_anything(self, sql: str, args: list[ValidSqlArgumentDescription] | None = None, fetch_rows: bool = True) -> tuple[int, list[dict[str, ValidSqlArgumentDescription]]]:
        if args is None:
            args = []
        try:
            return self.execute_with_reconnect(sql, args, fetch_rows)
        except MySQLdb.Warning as e:
            if e.args[0] in [1050, 1051]:
                return (0, [])  # we don't care if a CREATE IF NOT EXISTS raises an "already exists" warning or DROP TABLE IF NOT EXISTS raises an "unknown table" warning.
            if e.args[0] == 1062:
                return (0, [])  # We don't care if an INSERT IGNORE INTO didn't do anything.
            raise DatabaseException(f'Failed to execute `{sql}` with `{args}` because of `{e}`') from e
        except MySQLdb.Error as e:
            if e.args[0] == 2006:
                self.connect()
            raise DatabaseException(f'Failed to execute `{sql}` with `{args}` because of `{e}`') from e

    def execute_with_reconnect(self, sql: str, args: list[ValidSqlArgumentDescription] | None = None, fetch_rows: bool | None = False) -> tuple[int, list[ValidSqlArgumentDescription]]:
        result = None
        # Attempt to execute the query and reconnect 3 times, then give up
        for _ in range(3):
            try:
                p = perf.start()
                n = self.cursor.execute(sql, args)
                perf.check(p, 'slow_query', (f'```{sql}```', f'```{args}```'), 'mysql')
                if fetch_rows:
                    rows = self.cursor.fetchall()
                    result = (n, rows)
                else:
                    result = (n, [])
                break
            except OperationalError as e:
                if 'MySQL server has gone away' in str(e):
                    print('MySQL server has gone away: trying to reconnect')
                    self.connect()
                else:
                    # raise any other exception
                    raise
        else:
            # all attempts failed
            raise DatabaseException(f'Failed to execute `{sql}` with `{args}`. MySQL has gone away and it was not possible to reconnect in 3 attemps')
        return result

    def insert(self, sql: str, args: list[ValidSqlArgumentDescription] | None = None) -> int:
        self.execute(sql, args)
        return self.last_insert_rowid()

    def begin(self, label: str) -> None:
        print(f'Before BEGIN ({self.open_transactions})')
        if len(self.open_transactions) == 0:
            self.execute('BEGIN')
        self.open_transactions.append(label)
        print(f'After BEGIN ({self.open_transactions})')

    def commit(self, label: str) -> None:
        print(f'Before COMMIT ({self.open_transactions})')
        if len(self.open_transactions) == 1:
            self.execute('COMMIT')
        committed = self.open_transactions.pop()
        if committed != label:
            raise DatabaseException(f'Asked to commit `{committed}` to the db but was expecting to commit `{label}`.')
        print(f'After COMMIT ({self.open_transactions})')

    def rollback(self, label: str) -> None:
        print(f'Before ROLLBACK ({self.open_transactions}) in {label}')
        self.execute('ROLLBACK')
        self.open_transactions = []
        print(f'After ROLLBACK ({self.open_transactions}) in {label}')

    def last_insert_rowid(self) -> int:
        return cast(int, self.value('SELECT LAST_INSERT_ID()'))

    def get_lock(self, lock_id: str, timeout: int = 1) -> None:
        result = self.value('SELECT GET_LOCK(%s, %s)', [lock_id, timeout])
        if result != 1:
            raise LockNotAcquiredException

    def release_lock(self, lock_id: str) -> None:
        self.execute('SELECT RELEASE_LOCK(%s)', [lock_id])

    def value(self, sql: str, args: list[ValidSqlArgumentDescription] | None = None, default: Any | None = None, fail_on_missing: bool = False) -> Any:
        try:
            return self.values(sql, args)[0]
        except IndexError as c:
            if fail_on_missing:
                raise DatabaseMissingException(f'Failed to get a value from `{sql}` with `{args}') from c
            return default

    def values(self, sql: str, args: list[ValidSqlArgumentDescription] | None = None) -> list[Any]:
        rs = self.select(sql, args)
        return [list(row.values())[0] for row in rs]

    def close(self) -> None:
        if len(self.open_transactions) > 0:
            self.execute('ROLLBACK')
        self.cursor.close()
        self.connection.close()
        if len(self.open_transactions) > 0:
            raise DatabaseException(f'Closed database connection with open transactions `{self.open_transactions}` (they have been rolled back).')

    def nuke_database(self) -> None:
        self.begin('nuke_database')
        query = self.values("""
            SELECT concat('DROP TABLE IF EXISTS `', table_name, '`;')
            FROM information_schema.tables
            WHERE table_schema = %s;
        """, [self.name])
        self.execute('SET FOREIGN_KEY_CHECKS = 0')
        self.execute(''.join(query))
        self.execute('SET FOREIGN_KEY_CHECKS = 1')
        self.commit('nuke_database')

def get_database(location: str) -> Database:
    return Database(location)

def sqlescape(s: ValidSqlArgumentDescription, force_string: bool = False, backslashed_escaped: bool = False) -> ValidSqlArgumentDescription:
    if s is None:
        return 'NULL'
    if (str(s).isdecimal() or isinstance(s, float)) and not force_string:
        return s
    if isinstance(s, (str, int, float)):
        s = str(s)
        encodable = s.encode('utf-8', 'strict').decode('utf-8')
        if encodable.find('\x00') >= 0:
            raise Exception('NUL not allowed in SQL string.')
        if not backslashed_escaped:
            encodable = encodable.replace('\\', '\\\\')
        return "'{escaped}'".format(escaped=encodable.replace("'", "''").replace('%', '%%'))
    raise InvalidArgumentException(f'Cannot sqlescape `{s}`')

def sqllikeescape(s: str) -> str:
    s = s.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    return sqlescape(f'%{s}%', backslashed_escaped=True)

def concat(parts: Iterable[str]) -> str:
    return 'CONCAT(' + ', '.join(parts) + ')'
