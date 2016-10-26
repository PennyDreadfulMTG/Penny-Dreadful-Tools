import os
import sqlite3

from flask import g

from magic import configuration

class Database:
    # Bump this if you modify the schema.
    database = 1

    def __init__(self):
        self.verbose = False
        self.open()
        self.setup()

    def open(self):
        db = configuration.get('decksite_database')
        self.database = sqlite3.connect(db)
        self.database.row_factory = sqlite3.Row

    def close(self):
        self.database.close()

    def db_version(self) -> int:
        return self.value('SELECT version FROM db_version ORDER BY version DESC LIMIT 1', [], 0)

    def execute(self, sql, args=None):
        if self.verbose:
            print(sql)
        if args is None:
            args = []
        r = self.database.execute(sql, args).fetchall()
        self.database.commit()
        return r

    def value(self, sql, args=None, default=None):
        if args is None:
            args = []
        rs = self.database.execute(sql, args).fetchone()
        if rs is None:
            return default
        elif len(rs) <= 0:
            return default
        else:
            return rs[0]

    def setup(self, version=None):
        self.execute("CREATE TABLE IF NOT EXISTS db_version (version INTEGER UNIQUE ON CONFLICT REPLACE NOT NULL)")
        self.verbose = True
        if version is None:
            version = self.db_version()
        for fn in os.listdir('decksite/sql'):
            path = os.path.join('decksite/sql', fn)
            n = int(fn.split('.')[0])
            if version < n:
                print("Patching database to v{0}".format(n))
                fh = open(path, 'r')
                sql = fh.read()
                for stmt in sql.split(';'):
                    self.execute(stmt)
                fh.close()
                self.execute("INSERT INTO db_version (version) VALUES (?)", [n])

        self.verbose = False

def escape(s) -> str:
    if str(s).isdecimal():
        return s
    encodable = s.encode('utf-8', 'strict').decode('utf-8')
    if encodable.find('\x00') >= 0:
        raise Exception('NUL not allowed in SQL string.')
    return "'{escaped}'".format(escaped=encodable.replace("'", "''"))

def get_db():
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = Database()
    return g.sqlite_db
