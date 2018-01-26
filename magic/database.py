import flask
from flask import has_request_context, request

from magic import card
from shared import configuration
from shared.container import Container
from shared.database import get_database
from shared.pd_exception import DatabaseException

# Bump this if you modify the schema.
SCHEMA_VERSION = 97
DATABASE = Container()

def db():
    if flask.current_app:
        if has_request_context():
            context = request
        else:
            context = flask.g
    else:
        context = DATABASE
    if hasattr(context, 'magic_database'):
        return context.get('magic_database')
    context.magic_database = get_database(configuration.get('magic_database'))
    init()
    return context.get('magic_database')

def init():
    try:
        mtgjson_version()
        if db_version() < SCHEMA_VERSION:
            delete()
            setup()
    except DatabaseException:
        setup()

def mtgjson_version() -> str:
    return db().value('SELECT version FROM version', [], '0')

def db_version() -> int:
    return db().value('SELECT version FROM db_version', [], 0)

def setup():
    db().begin()
    db().execute('CREATE TABLE IF NOT EXISTS db_version (version INTEGER)')
    db().execute('CREATE TABLE IF NOT EXISTS version (version TEXT)')
    sql = create_table_def('card', card.card_properties())
    db().execute(sql)
    sql = create_table_def('face', card.face_properties())
    db().execute(sql)
    sql = create_table_def('set', card.set_properties())
    db().execute(sql)
    sql = create_table_def('color', card.color_properties())
    db().execute(sql)
    sql = create_table_def('card_color', card.card_color_properties())
    db().execute(sql)
    sql = create_table_def('card_color_identity', card.card_color_properties())
    db().execute(sql)
    sql = create_table_def('card_supertype', card.card_type_properties('supertype'))
    db().execute(sql)
    sql = create_table_def('card_type', card.card_type_properties('type'))
    db().execute(sql)
    sql = create_table_def('card_subtype', card.card_type_properties('subtype'))
    db().execute(sql)
    sql = create_table_def('format', card.format_properties())
    db().execute(sql)
    sql = create_table_def('card_legality', card.card_legality_properties())
    db().execute(sql)
    sql = create_table_def('card_alias', card.card_alias_properties())
    db().execute(sql)
    sql = create_table_def('card_bug', card.card_bug_properties())
    db().execute(sql)
    sql = create_table_def('rarity', card.format_properties()) # This has the same profile as `format` (`id`, `name`)
    db().execute(sql)
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
    # Speed up innermost subselect in base_query.
    db().execute('CREATE INDEX idx_card_id_format_id ON card_legality (card_id, format_id, legality)')
    db().execute('INSERT INTO db_version (version) VALUES ({0})'.format(SCHEMA_VERSION))
    db().commit()

# Drop the database so we can recreate it.
def delete():
    if db().is_sqlite():
        db().execute("PRAGMA writable_schema = 1")
        db().execute("DELETE FROM sqlite_master WHERE type IN ('table', 'index', 'trigger')")
        db().execute("PRAGMA writable_schema = 0;")
        db().execute("VACUUM")
    else:
        db().begin()
        query = db().values("""
        SELECT concat('DROP TABLE IF EXISTS `', table_name, '`;')
        FROM information_schema.tables
        WHERE table_schema = %s;
        """, [db().name])
        db().execute('SET FOREIGN_KEY_CHECKS = 0')
        db().execute(''.join(query))
        db().execute('SET FOREIGN_KEY_CHECKS = 1')
        db().commit()

def column_def(name, prop):
    if db().is_sqlite():
        nullable = 'NOT NULL' if not prop['nullable'] else ''
        primary_key = 'PRIMARY KEY' if prop['primary_key'] else ''
        default = 'DEFAULT {default}'.format(default=prop['default']) if prop['default'] is not None else ''
        unique = 'UNIQUE' if prop['unique'] else ''
        if prop['type'].startswith('VARCHAR') or prop['type'] == 'LONGTEXT':
            prop['type'] = 'TEXT'
        if prop['type'] == 'BOOLEAN':
            prop['type'] = 'INTEGER'
        return '`{name}` {type} {primary_key} {nullable} {unique} {default}'.format(name=name, type=prop['type'], primary_key=primary_key, nullable=nullable, unique=unique, default=default)
    elif db().is_mysql():
        nullable = 'NOT NULL' if not prop['nullable'] else ''
        primary_key = 'PRIMARY KEY AUTO_INCREMENT' if prop['primary_key'] else ''
        default = 'DEFAULT {default}'.format(default=prop['default']) if prop['default'] is not None else ''
        unique = 'UNIQUE' if prop['unique'] else ''
        return '`{name}` {type} {nullable} {primary_key} {unique} {default}'.format(name=name, type=prop['type'], primary_key=primary_key, nullable=nullable, unique=unique, default=default)
    else:
        raise DatabaseException('Unknown Database type')

def foreign_key_def(name, fk):
    return 'FOREIGN KEY(`{name}`) REFERENCES `{table}`(`{column}`)'.format(name=name, table=fk[0], column=fk[1])

def unique_constraint_def(name, cols):
    cols = [name] + cols
    return 'CONSTRAINT `{name}` UNIQUE ({cols})'.format(name='_'.join(cols), cols=', '.join('`{col}`'.format(col=col) for col in cols))

def create_table_def(name, props):
    sql = 'CREATE TABLE IF NOT EXISTS `{name}` ('
    sql += ', '.join(column_def(name, prop) for name, prop in props.items())
    fk = ', '.join(foreign_key_def(name, prop['foreign_key']) for name, prop in props.items() if prop['foreign_key'])
    uc = ', '.join(unique_constraint_def(name, prop['unique_with']) for name, prop in props.items() if prop['unique_with'])
    if fk:
        sql += ', ' + fk
    if uc:
        sql += ', ' + uc
    sql += ')'
    if db().is_mysql():
        sql += ' CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'
    return sql.format(name=name)
