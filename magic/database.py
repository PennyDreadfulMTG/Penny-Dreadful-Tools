import pkg_resources

from magic import card
from shared import configuration
from shared.database import Database
from shared.pd_exception import DatabaseException

# Bump this if you modify the schema.
SCHEMA_VERSION = 66

def db():
    return DATABASE

def init():
    try:
        version()
        if db_version() < SCHEMA_VERSION:
            delete()
            setup()
    except DatabaseException:
        setup()

def version() -> str:
    return pkg_resources.parse_version(db().value('SELECT version FROM version', [], '0'))

def db_version() -> int:
    return db().value('SELECT version FROM db_version', [], 0)

def setup():
    db().execute('CREATE TABLE IF NOT EXISTS db_version (version INTEGER)')
    db().execute('INSERT INTO db_version (version) VALUES ({0})'.format(SCHEMA_VERSION))
    db().execute('CREATE TABLE IF NOT EXISTS version (version TEXT)')
    sql = create_table_def('card', card.card_properties())
    db().execute(sql)
    sql = create_table_def('face', card.face_properties())
    db().execute(sql)
    sql = create_table_def('set', card.set_properties())
    db().execute(sql)
    db().execute('CREATE TABLE IF NOT EXISTS color (id INTEGER PRIMARY KEY, name TEXT, symbol TEXT)')
    db().execute("""CREATE TABLE IF NOT EXISTS card_color (
        id INTEGER PRIMARY KEY,
        card_id INTEGER NOT NULL,
        color_id INTEGER NOT NULL,
        FOREIGN KEY(card_id) REFERENCES card(id)
        FOREIGN KEY(color_id) REFERENCES color(id)
    )""")
    db().execute("""CREATE TABLE IF NOT EXISTS card_color_identity (
        id INTEGER PRIMARY KEY,
        card_id INTEGER NOT NULL,
        color_id INTEGER NOT NULL,
        FOREIGN KEY(card_id) REFERENCES card(id)
        FOREIGN KEY(color_id) REFERENCES color(id)
    )""")
    db().execute("""CREATE TABLE IF NOT EXISTS card_supertype (
        id INTEGER PRIMARY KEY,
        card_id INTEGER NOT NULL,
        supertype TEXT NOT NULL,
        FOREIGN KEY(card_id) REFERENCES card(id)
    )""")
    db().execute("""CREATE TABLE IF NOT EXISTS card_type (
        id INTEGER PRIMARY KEY,
        card_id INTEGER NOT NULL,
        type TEXT NOT NULL,
        FOREIGN KEY(card_id) REFERENCES card(id)
    )""")
    db().execute("""CREATE TABLE IF NOT EXISTS card_subtype (
        id INTEGER PRIMARY KEY,
        card_id INTEGER NOT NULL,
        subtype TEXT NOT NULL,
        FOREIGN KEY(card_id) REFERENCES card(id)
    )""")
    db().execute("""CREATE TABLE IF NOT EXISTS format (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL
    )""")
    db().execute("""CREATE TABLE IF NOT EXISTS card_legality (
        id INTEGER PRIMARY KEY,
        card_id INTEGER NOT NULL,
        format_id INTEGER NOT NULL,
        legality TEXT,
        FOREIGN KEY(card_id) REFERENCES card(id),
        FOREIGN KEY(format_id) REFERENCES format(id)
    )""")
    db().execute("""CREATE TABLE IF NOT EXISTS card_alias (
        id INTEGER PRIMARY KEY,
        card_id INTEGER NOT NULL,
        alias TEXT NOT NULL,
        FOREIGN KEY(card_id) REFERENCES card(id)
    )""")
    db().execute("""CREATE TABLE IF NOT EXISTS card_bugs (
        id INTEGER PRIMARY KEY,
        card_id INTEGER NOT NULL,
        description TEXT NOT NULL
        )""")
    db().execute("""CREATE TABLE IF NOT EXISTS rarity (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL
    )""")
    db().execute("""INSERT INTO color (name, symbol) VALUES
        ('White', 'W'),
        ('Blue', 'U'),
        ('Black', 'B'),
        ('Red', 'R'),
        ('Green', 'G')
    """)
    db().execute("""INSERT INTO rarity (name) VALUES
        ('Basic Land'),
        ('Common'),
        ('Uncommon'),
        ('Rare'),
        ('Mythic Rare')
    """)
    sql = create_table_def('printing', card.printing_properties())
    db().execute(sql)
    db().execute("""CREATE TABLE IF NOT EXISTS fetcher (
        id INTEGER PRIMARY KEY,
        resource TEXT UNIQUE ON CONFLICT REPLACE NOT NULL,
        last_modified TEXT,
        content TEXT
    )""")

# Drop the database so we can recreate it.
def delete():
    db().execute("PRAGMA writable_schema = 1")
    db().execute("DELETE FROM sqlite_master WHERE type IN ('table', 'index', 'trigger')")
    db().execute("PRAGMA writable_schema = 0;")
    db().execute("VACUUM")

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
