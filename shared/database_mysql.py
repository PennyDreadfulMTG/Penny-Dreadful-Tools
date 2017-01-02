import MySQLdb

from magic import card
from shared import configuration
from shared.pd_exception import DatabaseException

class Database:
    def __init__(self, db):
        try:
            host = configuration.get('mysql_host')
            port = configuration.get('mysql_port')
            user = configuration.get('mysql_user')
            passwd = configuration.get('mysql_passwd')
            self.connection = MySQLdb.connect(host=host, port=port, user=user, passwd=passwd)
            # self.connection.createscalarfunction('unaccent', card.unaccent, 1)
            self.cursor = self.connection.cursor(MySQLdb.cursors.DictCursor)
            try:
                self.execute("USE {db}".format(db=db))
            except DatabaseException:
                self.execute("CREATE DATABASE {db}".format(db=db))
                self.execute("USE  {db}".format(db=db))
        except MySQLdb.Error as e:
            raise DatabaseException('Failed to initialized database in `{location}`'.format(location=db)) from e

    def execute(self, sql, args=None):
        # print(sql)
        if args is None:
            args = []
        try:
            self.cursor.execute(sql, args)
            return self.cursor.fetchall()
        except MySQLdb.Error as e:
            # Quick fix for league bugs
            if "cannot start a transaction within a transaction" in str(e):
                self.execute("ROLLBACK")
                if sql == "BEGIN TRANSACTION":
                    return self.cursor.execute(sql, args).fetchall()
            raise DatabaseException('Failed to execute `{sql}` because of `{e}`'.format(sql=sql, e=e)) from e

    def value(self, sql, args=None, default=None, fail_on_missing=False):
        try:
            return self.values(sql, args)[0]
        except IndexError as e:
            if fail_on_missing:
                raise DatabaseException('Failed to get a value from `{sql}`'.format(sql=sql)) from e
            else:
                return default

    def values(self, sql, args=None):
        rs = self.execute(sql, args)
        return [list(row.values())[0] for row in rs]

    def insert(self, sql, args=None):
        self.execute(sql, args)
        return self.value('SELECT LAST_INSERT_ID()')

    def begin(self):
        self.connection.begin()

    def commit(self):
        self.connection.commit()

def row_factory(cursor, row):
    columns = [t[0] for t in cursor.getdescription()]
    return dict(zip(columns, row))
