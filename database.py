import sqlite3

import pkg_resources

import card
import configuration

class Database:
    # Bump this if you modify the schema.
    schema_version = 27

    @staticmethod
    def escape(s) -> str:
        if str(s).isdecimal():
            return s
        encodable = s.encode('utf-8', 'strict').decode('utf-8')
        if encodable.find('\x00') >= 0:
            raise Exception('NUL not allowed in SQL string.')
        return "'{escaped}'".format(escaped=encodable.replace("'", "''"))

    def __init__(self):
        self.open()
        try:
            self.version()
            if self.db_version() < self.schema_version:
                self.delete()
                self.setup()
        except sqlite3.OperationalError:
            self.setup()

    def open(self):
        db = configuration.get('database')
        self.database = sqlite3.connect(db)
        self.database.row_factory = sqlite3.Row

    def version(self) -> str:
        return pkg_resources.parse_version(self.value('SELECT version FROM version', [], '0'))

    def db_version(self) -> int:
        return self.value('SELECT version FROM db_version', [], '0')

    def execute(self, sql, args=None):
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

    def setup(self):
        self.execute('CREATE TABLE IF NOT EXISTS db_version (version INTEGER)')
        self.execute('INSERT INTO db_version (version) VALUES ({0})'.format(self.schema_version))
        self.execute('CREATE TABLE IF NOT EXISTS version (version TEXT)')
        sql = 'CREATE TABLE IF NOT EXISTS card (id INTEGER PRIMARY KEY, pd_legal INTEGER, '
        sql += ', '.join('{name} {type}'.format(name=name, type=type) for name, type in card.properties().items())
        sql += ')'
        self.execute(sql)
        self.execute("""CREATE TABLE IF NOT EXISTS card_name (
            id INTEGER PRIMARY KEY,
            card_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            FOREIGN KEY(card_id) REFERENCES card(id)
        )""")
        sql = 'CREATE TABLE IF NOT EXISTS `set` (id INTEGER PRIMARY KEY, '
        sql += ', '.join('{name} {type}'.format(name=name, type=type) for name, type in card.set_properties().items())
        sql += ')'
        self.execute(sql)
        sql = 'CREATE TABLE IF NOT EXISTS printing ('
        sql += 'id INTEGER PRIMARY KEY,'
        sql += 'card_id INTEGER NOT NULL, '
        sql += 'set_id INTEGER NOT NULL, '
        sql += 'rarity_id INTEGER, '
        sql += ', '.join('{name} {type}'.format(name=name, type=type) for name, type in card.printing_properties().items())
        sql += ', FOREIGN KEY(card_id) REFERENCES card(id), '
        sql += 'FOREIGN KEY(set_id) REFERENCES `set`(id))'
        self.execute(sql)
        self.execute('CREATE TABLE IF NOT EXISTS color (id INTEGER PRIMARY KEY, name TEXT, symbol TEXT)')
        self.execute("""CREATE TABLE IF NOT EXISTS card_color (
            id INTEGER PRIMARY KEY,
            card_id INTEGER NOT NULL,
            color_id INTEGER NOT NULL,
            FOREIGN KEY(card_id) REFERENCES card(id)
            FOREIGN KEY(color_id) REFERENCES color(id)
        )""")
        self.execute("""CREATE TABLE IF NOT EXISTS card_color_identity (
            id INTEGER PRIMARY KEY,
            card_id INTEGER NOT NULL,
            color_id INTEGER NOT NULL,
            FOREIGN KEY(card_id) REFERENCES card(id)
            FOREIGN KEY(color_id) REFERENCES color(id)
        )""")
        self.execute("""CREATE TABLE IF NOT EXISTS card_supertype (
            id INTEGER PRIMARY KEY,
            card_id INTEGER NOT NULL,
            supertype TEXT NOT NULL,
            FOREIGN KEY(card_id) REFERENCES card(id)
        )""")
        self.execute("""CREATE TABLE IF NOT EXISTS card_type (
            id INTEGER PRIMARY KEY,
            card_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            FOREIGN KEY(card_id) REFERENCES card(id)
        )""")
        self.execute("""CREATE TABLE IF NOT EXISTS card_subtype (
            id INTEGER PRIMARY KEY,
            card_id INTEGER NOT NULL,
            subtype TEXT NOT NULL,
            FOREIGN KEY(card_id) REFERENCES card(id)
        )""")
        self.execute("""CREATE TABLE IF NOT EXISTS format (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        )""")
        self.execute("""CREATE TABLE IF NOT EXISTS card_legality (
            id INTEGER PRIMARY KEY,
            card_id INTEGER NOT NULL,
            format_id INTEGER NOT NULL,
            FOREIGN KEY(card_id) REFERENCES card(id),
            FOREIGN KEY(format_id) REFERENCES format(id)
        )""")
        self.execute("""CREATE TABLE IF NOT EXISTS card_alias (
            id INTEGER PRIMARY KEY,
            card_id INTEGER NOT NULL,
            alias TEXT NOT NULL,
            FOREIGN KEY(card_id) REFERENCES card(id)
        )""")
        self.execute("""CREATE TABLE IF NOT EXISTS rarity (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        )""")
        self.execute("""INSERT INTO color (name, symbol) VALUES
            ('White', 'W'),
            ('Blue', 'U'),
            ('Black', 'B'),
            ('Red', 'R'),
            ('Green', 'G')
        """)
        self.execute("""INSERT INTO rarity (name) VALUES
            ('Basic Land'),
            ('Common'),
            ('Uncommon'),
            ('Rare'),
            ('Mythic Rare')
        """)
        self.execute("""CREATE TABLE IF NOT EXISTS fetcher (
            id INTEGER PRIMARY KEY,
            resource TEXT UNIQUE ON CONFLICT REPLACE NOT NULL,
            last_modified TEXT
        )""")


    # Drop the database so we can recreate it.
    def delete(self):
        self.execute("PRAGMA writable_schema = 1")
        self.execute("delete from sqlite_master where type in ('table', 'index', 'trigger')")
        self.execute("PRAGMA writable_schema = 0;")
        self.execute("VACUUM")
