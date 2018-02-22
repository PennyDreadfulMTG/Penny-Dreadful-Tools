# pylint: disable=import-error, duplicate-code
import warnings

import MySQLdb
from MySQLdb import OperationalError

from shared import configuration, perf
from shared.database_generic import GenericDatabase
from shared.pd_exception import DatabaseException, LockNotAcquiredException


class MysqlDatabase(GenericDatabase):
    def __init__(self, db):
        warnings.filterwarnings('error', category=MySQLdb.Warning)
        self.name = db
        self.host = configuration.get('mysql_host')
        self.port = configuration.get('mysql_port')
        if str(self.port).startswith('0.0.0.0:'):
            # Thanks Docker :/
            self.port = int(self.port[8:])
        self.user = configuration.get('mysql_user')
        self.passwd = configuration.get('mysql_passwd')
        self.connect()

    def connect(self):
        try:
            self.connection = MySQLdb.connect(host=self.host, port=self.port, user=self.user, passwd=self.passwd, use_unicode=True, charset='utf8', autocommit=True)
            self.cursor = self.connection.cursor(MySQLdb.cursors.DictCursor)
            self.execute('SET NAMES utf8mb4')
            try:
                self.execute("USE {db}".format(db=self.name))
            except DatabaseException:
                print('Creating database {db}'.format(db=self.name))
                self.execute('CREATE DATABASE {db} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'.format(db=self.name))
                self.execute('USE {db}'.format(db=self.name))
        except MySQLdb.Error:
            raise DatabaseException('Failed to initialize database in `{location}`'.format(location=self.name))

    def execute(self, sql, args=None):
        sql = sql.replace('COLLATE NOCASE', '') # Needed for case insensitivity in SQLite which is default in MySQL.
        if args is None:
            args = []
        if args:
            # eww
            sql = sql.replace('?', '%s')
        try:
            return self.execute_with_reconnect(sql, args)
        except MySQLdb.Warning as e:
            if e.args[0] == 1050 or e.args[0] == 1051:
                pass # we don't care if a CREATE IF NOT EXISTS raises an "already exists" warning or DROP TABLE IF NOT EXISTS raises an "unknown table" warning.
            elif e.args[0] == 1062:
                pass # We don't care if an INSERT IGNORE INTO didn't do anything.
            else:
                raise DatabaseException('Failed to execute `{sql}` with `{args}` because of `{e}`'.format(sql=sql, args=args, e=e))
        except MySQLdb.Error as e:
            raise DatabaseException('Failed to execute `{sql}` with `{args}` because of `{e}`'.format(sql=sql, args=args, e=e))

    def execute_with_reconnect(self, sql, args):
        result = None
        # Attempt to excute the query and reconnect 3 times, then give up
        for _ in range(3):
            try:
                p = perf.start()
                self.cursor.execute(sql, args)
                perf.check(p, 'slow_query', (sql, args), 'mysql')
                result = self.cursor.fetchall()
                break
            except OperationalError as e:
                if 'MySQL server has gone away' in str(e):
                    print("MySQL server has gone away: trying to reconnect")
                    self.connect()
                else:
                    # raise any other exception
                    raise e
        else:
            # all attempts failed
            raise DatabaseException('Failed to execute `{sql}` with `{args}`. MySQL has gone away and it was not possible to reconnect in 3 attemps'.format(sql=sql, args=args))
        return result

    def insert(self, sql, args=None):
        self.execute(sql, args)
        return self.last_insert_rowid()

    def begin(self):
        self.connection.begin()

    def commit(self):
        self.connection.commit()

    def last_insert_rowid(self):
        return self.value('SELECT LAST_INSERT_ID()')

    # pylint: disable=no-self-use
    def concat(self, parts):
        return 'CONCAT(' + ', '.join(parts) + ')'

    # pylint: disable=no-self-use
    def is_mysql(self):
        return True

    # pylint: disable=no-self-use
    def supports_lock(self):
        return True

    def get_lock(self, lock_id, timeout=4):
        result = self.value('select get_lock(%s, %s)', [lock_id, timeout])
        if result != 1:
            raise LockNotAcquiredException

    def release_lock(self, lock_id):
        self.execute('select release_lock(%s)', [lock_id])

    def create_index_query(self, name, table, column, prefix_width=None):
        if prefix_width is not None:
            width = '({w})'.format(w=prefix_width)
        else:
            width = ''
        return 'CREATE INDEX {name} on {table} ({column}{width})'.format(name=name, table=table, column=column, width=width)
