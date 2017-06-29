#pylint: disable=import-error, duplicate-code
import MySQLdb

from shared import configuration
from shared.database_generic import GenericDatabase
from shared.pd_exception import DatabaseException

class MysqlDatabase(GenericDatabase):
    def __init__(self, db):
        try:
            self.name = db
            host = configuration.get('mysql_host')
            port = configuration.get('mysql_port')
            if str(port).startswith('0.0.0.0:'):
                # Thanks Docker :/
                port = int(port[8:])
            user = configuration.get('mysql_user')
            passwd = configuration.get('mysql_passwd')
            self.connection = MySQLdb.connect(host=host, port=port, user=user, passwd=passwd, use_unicode=True, charset='utf8', autocommit=True)
            # self.connection.createscalarfunction('unaccent', card.unaccent, 1)
            self.cursor = self.connection.cursor(MySQLdb.cursors.DictCursor)
            try:
                self.execute("USE {db}".format(db=db))
            except DatabaseException:
                print('creating Database {db}'.format(db=db))
                self.execute("CREATE DATABASE {db}".format(db=db))
                self.execute("USE {db}".format(db=db))
        except MySQLdb.Error as e:
            raise DatabaseException('Failed to initialize database in `{location}`'.format(location=db)) from e

    def execute(self, sql, args=None):
        if args is None:
            args = []
        if args:
            # eww
            sql = sql.replace('?', '%s')
        try:
            self.cursor.execute(sql, args)
            return self.cursor.fetchall()
        except MySQLdb.Error as e:
            raise DatabaseException('Failed to execute `{sql}` because of `{e}`'.format(sql=sql, e=e)) from e

    def insert(self, sql, args=None):
        self.execute(sql, args)
        return self.value('SELECT LAST_INSERT_ID()')

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
