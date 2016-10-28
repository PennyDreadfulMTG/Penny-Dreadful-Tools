import apsw
import pkg_resources

from magic import card
from magic import configuration

class Database:
    # Bump this if you modify the schema.
    schema_version = 62

    def __init__(self):
        self.open()
        try:
            self.version()
            if self.db_version() < self.schema_version:
                self.delete()
                self.setup()
        except apsw.SQLError:
            self.setup()

    def open(self):
        db = configuration.get('database')
        self.connection = apsw.Connection(db)
        self.connection.setrowtrace(row_factory)
        self.connection.enableloadextension(True)
        self.connection.loadextension(configuration.get('spellfix'))
        self.connection.createscalarfunction('unaccent', card.unaccent, 1)
        self.cursor = self.connection.cursor()

    def version(self) -> str:
        return pkg_resources.parse_version(self.value('SELECT version FROM version', [], '0'))

    def db_version(self) -> int:
        return self.value('SELECT version FROM db_version', [], 0)

    def execute(self, sql, args=None):
        if args is None:
            args = []
        return self.cursor.execute(sql, args).fetchall()

    def value(self, sql, args=None, default=None):
        if args is None:
            args = []
        rs = self.cursor.execute(sql, args).fetchone()
        if rs is None:
            return default
        elif len(rs) <= 0:
            return default
        else:
            return list(rs.values())[0]

    def setup(self):
        self.execute('CREATE TABLE IF NOT EXISTS db_version (version INTEGER)')
        self.execute('INSERT INTO db_version (version) VALUES ({0})'.format(self.schema_version))
        self.execute('CREATE TABLE IF NOT EXISTS version (version TEXT)')
        sql = create_table_def('card', card.card_properties())
        self.execute(sql)
        sql = create_table_def('face', card.face_properties())
        self.execute(sql)
        sql = create_table_def('set', card.set_properties())
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
            legality TEXT,
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
        sql = create_table_def('printing', card.printing_properties())
        self.execute(sql)
        self.execute("""CREATE TABLE IF NOT EXISTS fetcher (
            id INTEGER PRIMARY KEY,
            resource TEXT UNIQUE ON CONFLICT REPLACE NOT NULL,
            last_modified TEXT,
            content TEXT
        )""")

    # Drop the database so we can recreate it.
    def delete(self):
        self.execute("PRAGMA writable_schema = 1")
        self.execute("DELETE FROM sqlite_master WHERE type IN ('table', 'index', 'trigger')")
        self.execute("PRAGMA writable_schema = 0;")
        self.execute("VACUUM")

def escape(s) -> str:
    if str(s).isdecimal():
        return s
    encodable = s.encode('utf-8', 'strict').decode('utf-8')
    if encodable.find('\x00') >= 0:
        raise Exception('NUL not allowed in SQL string.')
    return "'{escaped}'".format(escaped=encodable.replace("'", "''"))

def row_factory(cursor, row):
    columns = [t[0] for t in cursor.getdescription()]
    return dict(zip(columns, row))

def column_def(name, prop):
    nullable = 'NOT NULL' if not prop['nullable'] else ''
    primary_key = 'PRIMARY KEY' if prop['primary_key'] else ''
    default = 'DEFAULT {default}'.format(default=prop['default']) if prop['default'] is not None else ''
    unique = 'UNIQUE' if prop['unique'] else ''
    return '`{name}` {type} {primary_key} {nullable} {unique} {default}'.format(name=name, type=prop['type'], primary_key=primary_key, nullable=nullable, unique=unique, default=default)

def foreign_key_def(name, fk):
    return 'FOREIGN KEY(`{name}`) REFERENCES `{table}`(`{column}`)'.format(name=name, table=fk[0], column=fk[1])

def create_table_def(name, props):
    sql = 'CREATE TABLE IF NOT EXISTS `{name}` ('
    sql += ', '.join(column_def(name, prop) for name, prop in props.items())
    fk = ', '.join(foreign_key_def(name, prop['foreign_key']) for name, prop in props.items() if prop['foreign_key'])
    if fk:
        sql += ', ' + fk
    sql += ')'
    return sql.format(name=name)

DATABASE = Database(configuration.get('magic_database'))
init()
