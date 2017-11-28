import apsw

from shared import configuration, perf
from shared.database_generic import GenericDatabase
from shared.pd_exception import DatabaseException

class SqliteDatabase(GenericDatabase):
    def __init__(self, location):
        try:
            self.name = location
            self.connection = apsw.Connection(location)
            self.connection.setrowtrace(row_factory)
            self.connection.enableloadextension(True)
            self.connection.loadextension(configuration.get('spellfix'))
            self.cursor = self.connection.cursor()
        except apsw.Error as e:
            raise DatabaseException('Failed to initialize database in `{location}`'.format(location=location)) from e

    def execute(self, sql, args=None):
        sql = sql.replace('MEDIUMINT UNSIGNED', 'INTEGER') # Column type difference.
        sql = sql.replace(' SEPARATOR ', ', ') # MySQL/SQLite GROUP_CONCAT syntax difference.
        sql = sql.replace('INSERT IGNORE', 'INSERT OR IGNORE') # MySQL/SQLite difference.
        sql = sql.replace('%%', '%') # MySQLDB and apsw escaping difference.
        if args is None:
            args = []
        try:
            p = perf.start()
            result = self.cursor.execute(sql, args)
            perf.check(p, 'slow_query', (sql, args), 'sqlite')
            return result.fetchall()
        except apsw.Error as e:
            # Quick fix for league bugs
            if "cannot start a transaction within a transaction" in str(e):
                self.execute("ROLLBACK")
                if sql == "BEGIN TRANSACTION":
                    return self.cursor.execute(sql, args).fetchall()
            raise DatabaseException('Failed to execute `{sql}` with `{args}` because of `{e}`'.format(sql=sql, args=args, e=e)) from e

    def insert(self, sql, args=None):
        self.execute(sql, args)
        return self.value('SELECT last_insert_rowid()')

    def begin(self):
        self.execute("BEGIN TRANSACTION")

    def commit(self):
        self.execute("COMMIT")

    def last_insert_rowid(self):
        return self.value('SELECT last_insert_rowid()')

    # pylint: disable=no-self-use
    def concat(self, parts):
        return ' || '.join(parts)

    # pylint: disable=no-self-use
    def is_sqlite(self):
        return True


def row_factory(cursor, row):
    columns = [t[0] for t in cursor.getdescription()]
    return dict(zip(columns, row))
