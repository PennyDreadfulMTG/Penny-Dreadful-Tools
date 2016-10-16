import datetime
import re

import card
import database
import fetcher

def layouts():
    return ['normal', 'meld', 'split', 'phenomenon', 'token', 'vanguard', 'double-faced', 'plane', 'flip', 'scheme', 'leveler']


CARD_IDS = {}
FORMAT_IDS = {}
DATABASE = database.DATABASE
def initialize():
    current_version = fetcher.version()
    if current_version > DATABASE.version():
        print('Database update required')
        update_database(str(current_version))
    aliases = fetcher.card_aliases()
    if DATABASE.alias_count() != len(aliases):
        print('Card alias update required')
        update_card_aliases(aliases)

def search(query):
    sql = 'SELECT word, distance FROM fuzzy WHERE word MATCH ?'
    rs = DATABASE.execute(sql, ['*{query}*'.format(query=query)])
    sql = 'SELECT card.id, ' + (', '.join(property for property in card.properties())) \
        + ', alias ' \
        + ' FROM card LEFT OUTER JOIN card_alias on card.id = card_alias.card_id ' \
        + 'WHERE name IN (SELECT word FROM fuzzy WHERE word MATCH ? AND distance <= 200) ' \
        + 'ORDER BY pd_legal DESC, name'
    rs = DATABASE.execute(sql, ['*{query}*'.format(query=query)])
    return [card.Card(r) for r in rs]

def get_legal_cards(force=False):
    new_list = ['']
    fetcher.legal_cards(force)
    if new_list == ['']:
        new_list = [card.Card(r).name.lower() for r in DATABASE.execute('SELECT name FROM card WHERE pd_legal = 1')]
        if len(new_list) == 0:
            new_list = fetcher.legal_cards(force=True)
            DATABASE.execute('UPDATE card SET pd_legal = 0')
            DATABASE.execute('UPDATE card SET pd_legal = 1 WHERE LOWER(name) IN (' + ', '.join(database.escape(name) for name in new_list) + ')')
    else:
        DATABASE.execute('UPDATE card SET pd_legal = 0')
        DATABASE.execute('UPDATE card SET pd_legal = 1 WHERE LOWER(name) IN (' + ', '.join(database.escape(name) for name in new_list) + ')')
    return new_list

def update_database(new_version):
    DATABASE.execute('BEGIN TRANSACTION')
    DATABASE.execute('DELETE FROM version')
    cards = fetcher.all_cards()
    for _, c in cards.items():
        insert_card(c)
    sets = fetcher.all_sets()
    for _, s in sets.items():
        insert_set(s)
    # mtgjson thinks that lands have a CMC of NULL so we'll work around that here.
    check_layouts() # Check that the hardcoded list of layouts we're about to use is still valid.
    DATABASE.execute("UPDATE card SET cmc = 0 WHERE cmc IS NULL AND layout IN ('normal', 'double-faced', 'flip', 'leveler', 'token', 'split')")
    rs = DATABASE.execute('SELECT id, name FROM rarity')
    for row in rs:
        DATABASE.execute('UPDATE printing SET rarity_id = ? WHERE rarity = ?', [row['id'], row['name']])
    update_fuzzy_matching()
    DATABASE.execute('INSERT INTO version (version) VALUES (?)', [new_version])
    DATABASE.execute('COMMIT')

def update_card_aliases(aliases):
    DATABASE.execute('DELETE FROM card_alias', [])
    for alias, name in aliases:
        card_id = DATABASE.value('SELECT id FROM card WHERE name = ?', [name])
        if card_id is not None:
            DATABASE.execute('INSERT INTO card_alias (card_id, alias) VALUES (?, ?)', [card_id, alias])
        else:
            print("no card found named " + name + " for alias " + alias)

def update_fuzzy_matching():
    DATABASE.execute('DROP TABLE IF EXISTS fuzzy')
    DATABASE.execute('CREATE VIRTUAL TABLE IF NOT EXISTS fuzzy USING spellfix1')
    DATABASE.execute('INSERT INTO fuzzy(word, rank) SELECT name, pd_legal FROM card')

def insert_card(c):
    sql = 'INSERT INTO card ('
    sql += ', '.join(prop for prop in card.properties())
    sql += ', name_ascii'
    sql += ') VALUES ('
    sql += ', '.join('?' for prop in card.properties())
    sql += ', ?'
    sql += ')'
    values = [c.get(database2json(prop)) for prop in card.properties()] + [command.unaccent(c.get('name'))]
    # database.execute commits after each statement, which we want to
    # avoid while inserting cards
    DATABASE.database.execute(sql, values)
    card_id = DATABASE.value('SELECT last_insert_rowid()')
    CARD_IDS[c.get('name')] = card_id
    for name in c.get('names', []):
        DATABASE.database.execute('INSERT INTO card_name (card_id, name) VALUES (?, ?)', [card_id, name])
    for color in c.get('colors', []):
        color_id = DATABASE.value('SELECT id FROM color WHERE name = ?', [color])
        DATABASE.database.execute('INSERT INTO card_color (card_id, color_id) VALUES (?, ?)', [card_id, color_id])
    for symbol in c.get('colorIdentity', []):
        color_id = DATABASE.value('SELECT id FROM color WHERE symbol = ?', [symbol])
        DATABASE.database.execute('INSERT INTO card_color_identity (card_id, color_id) VALUES (?, ?)', [card_id, color_id])
    for supertype in c.get('supertypes', []):
        DATABASE.database.execute('INSERT INTO card_supertype (card_id, supertype) VALUES (?, ?)', [card_id, supertype])
    for subtype in c.get('subtypes', []):
        DATABASE.database.execute('INSERT INTO card_subtype (card_id, subtype) VALUES (?, ?)', [card_id, subtype])
    for info in c.get('legalities', []):
        format_id = get_format_id(info['format'], True)
        DATABASE.database.execute('INSERT INTO card_legality (card_id, format_id, legality) VALUES (?, ?, ?)', [card_id, format_id, info['legality']])

def insert_set(s) -> None:
    sql = 'INSERT INTO `set` ('
    sql += ', '.join(prop for prop in card.set_properties())
    sql += ') VALUES ('
    sql += ', '.join('?' for prop in card.set_properties())
    sql += ')'
    values = [date2int(s.get(underscore2camel(prop))) for prop in card.set_properties()]
    # database.execute commits after each statement, which we want to
    # avoid while inserting sets
    DATABASE.database.execute(sql, values)
    set_id = DATABASE.value('SELECT last_insert_rowid()')
    for c in s.get('cards', []):
        card_id = CARD_IDS[c.get('name')]
        sql = 'INSERT INTO printing (card_id, set_id, '
        sql += ', '.join(prop for prop in card.printing_properties())
        sql += ') VALUES (?, ?, '
        sql += ', '.join('?' for prop in card.printing_properties())
        sql += ')'
        values = [card_id, set_id] + [c.get(database2json(prop)) for prop in card.printing_properties()]
        DATABASE.database.execute(sql, values)

def get_format_id(name, allow_create=False):
    if len(FORMAT_IDS) == 0:
        rs = DATABASE.execute('SELECT id, name FROM format')
        for row in rs:
            FORMAT_IDS[row['name']] = row['id']
    if name not in FORMAT_IDS.keys() and allow_create:
        DATABASE.execute('INSERT INTO format (name) VALUES (?)', [name])
        FORMAT_IDS[name] = DATABASE.value('SELECT last_insert_rowid()')
    if name not in FORMAT_IDS.keys():
        return None
    return FORMAT_IDS[name]

def check_layouts():
    rs = DATABASE.execute('SELECT DISTINCT layout FROM card')
    if sorted([row['layout'] for row in rs]) != sorted(layouts()):
        print('WARNING. There has been a change in layouts. The update to 0 CMC may no longer be valid.')

def get_printings(generalized_card: card.Card):
    sql = 'SELECT ' + (', '.join(property for property in card.printing_properties())) \
        + ' FROM printing ' \
        + ' WHERE card_id = ? ' \

    rs = DATABASE.execute(sql, [generalized_card.id])
    return [card.Printing(r) for r in rs]

def database2json(propname: str) -> str:
    if propname == "system_id":
        propname = "id"
    return underscore2camel(propname)

def underscore2camel(s):
    return re.sub(r'(?!^)_([a-zA-Z])', lambda m: m.group(1).upper(), s)

def date2int(s):
    try:
        dt = datetime.datetime.strptime(str(s), '%Y-%m-%d')
        return dt.replace(tzinfo=datetime.timezone.utc).timestamp()
    except ValueError:
        return s

initialize()
