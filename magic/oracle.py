import datetime
import re

from magic import card
from magic import database
from magic import fetcher

CARD_IDS = {}
FORMAT_IDS = {}
DATABASE = database.DATABASE

def layouts():
    return ['normal', 'meld', 'split', 'phenomenon', 'token', 'vanguard', 'double-faced', 'plane', 'flip', 'scheme', 'leveler']

def initialize():
    current_version = fetcher.mtgjson_version()
    if current_version > DATABASE.version():
        print('Database update required')
        update_database(str(current_version))

def search(query):
    query = card.canonicalize(query)
    # 260 makes 'Odds/Ends' match 'Odds // Ends' so that's what we're using for our spellfix1 threshold here.
    fuzzy_threshold = 260
    sql = """
        {base_select}
        HAVING LOWER({name_select}) IN (SELECT word FROM fuzzy WHERE word MATCH ? AND distance <= {fuzzy_threshold})
            OR {name_ascii_select} LIKE ?
            OR SUM(CASE WHEN LOWER(face_name) IN (SELECT word FROM fuzzy WHERE word MATCH ? AND distance <= {fuzzy_threshold}) THEN 1 ELSE 0 END) > 0
        ORDER BY pd_legal DESC, name
    """.format(base_select=base_select(), name_select=card.name_select().format(table='u'), name_ascii_select=card.name_select('name_ascii').format(table='u'), fuzzy_threshold=fuzzy_threshold)
    fuzzy_query = '{query}*'.format(query=query)
    like_query = '%{query}%'.format(query=query)
    rs = DATABASE.execute(sql, [fuzzy_query, like_query, fuzzy_query])
    return [card.Card(r) for r in rs]

def load_cards(names):
    sql = """
        {base_select}
        HAVING LOWER({name_select}) IN ({names})
    """.format(base_select=base_select(), name_select=card.name_select().format(table='u'), names=', '.join(database.escape(name).lower() for name in names))
    rs = DATABASE.execute(sql)
    return [card.Card(r) for r in rs]

def base_select(where_clause='(1 = 1)'):
    return """
        SELECT
            {card_selects},
            {face_selects},
            GROUP_CONCAT(face_name, '|') AS names,
            SUM(CASE WHEN format_id = {format_id} THEN 1 ELSE 0 END) > 0 AS pd_legal
            FROM
                (SELECT {card_props}, {face_props}, f.name AS face_name, cl.format_id
                FROM card AS c
                INNER JOIN face AS f ON c.id = f.card_id
                LEFT OUTER JOIN card_legality AS cl ON c.id = cl.card_id AND cl.format_id = {format_id}
                ORDER BY f.card_id, f.position)
            AS u
            WHERE id IN (SELECT c.id FROM card AS c INNER JOIN face AS f ON c.id = f.card_id WHERE {where_clause})
            GROUP BY id
    """.format(
        card_selects=', '.join(prop['select'].format(table='u', column=name) for name, prop in card.card_properties().items()),
        face_selects=', '.join(prop['select'].format(table='u', column=name) for name, prop in card.face_properties().items()),
        format_id=get_format_id('Penny Dreadful'),
        card_props=', '.join('c.{name}'.format(name=name) for name in card.card_properties()),
        face_props=', '.join('f.{name}'.format(name=name) for name in card.face_properties() if name not in ['id', 'name']),
        where_clause=where_clause)

def get_legal_cards(force=False):
    new_list = ['']
    try:
        new_list = fetcher.legal_cards(force)
    except fetcher.FetchException:
        pass
    if new_list == ['']:
        sql = '{base_select} HAVING pd_legal = 1'.format(base_select=base_select())
        new_list = [r['name'] for r in DATABASE.execute(sql)]
        if len(new_list) == 0:
            new_list = fetcher.legal_cards(force=True)
    format_id = get_format_id('Penny Dreadful')
    DATABASE.execute('DELETE FROM card_legality WHERE format_id = ?', [format_id])
    sql = """INSERT INTO card_legality (format_id, card_id, legality)
        SELECT {format_id}, id, 'Legal'
        FROM ({base_select})
        WHERE name IN ({names})
    """.format(format_id=format_id, base_select=base_select(), names=', '.join(database.escape(name) for name in new_list))
    DATABASE.execute(sql)
    # Check we got the right number of legal cards.
    n = DATABASE.value('SELECT COUNT(*) FROM card_legality WHERE format_id = ?', [format_id])
    if n != len(new_list):
        print("Found {n} pd legal cards in the database but the list was {len} long".format(n=n, len=len(new_list)))
        sql = 'SELECT name FROM ({base_select}) WHERE id IN (SELECT card_id FROM card_legality WHERE format_id = {format_id})'.format(base_select=base_select(), format_id=format_id)
        db_legal_list = [row['name'] for row in DATABASE.execute(sql)]
        print(set(new_list).symmetric_difference(set(db_legal_list)))
    return new_list

def update_database(new_version):
    DATABASE.execute('BEGIN TRANSACTION')
    DATABASE.execute('DELETE FROM version')
    cards = fetcher.all_cards()
    melded_faces = []
    for _, c in cards.items():
        if c.get('layout') == 'meld' and c.get('name') == c.get('names')[2]:
            melded_faces.append(c)
        else:
            insert_card(c)
    for face in melded_faces:
        insert_card(face)
        first, second = face['names'][0:2]
        face['names'][0] = second
        face['names'][1] = first
        insert_card(face)
    sets = fetcher.all_sets()
    for _, s in sets.items():
        insert_set(s)
    check_layouts() # Check that the hardcoded list of layouts we're about to use is still valid.
    # mtgjson thinks that lands have a CMC of NULL so we'll work around that here.
    DATABASE.execute("UPDATE face SET cmc = 0 WHERE cmc IS NULL AND card_id IN (SELECT id FROM card WHERE layout IN ('normal', 'double-faced', 'flip', 'leveler', 'token', 'split'))")
    rs = DATABASE.execute('SELECT id, name FROM rarity')
    for row in rs:
        DATABASE.execute('UPDATE printing SET rarity_id = ? WHERE rarity = ?', [row['id'], row['name']])
    update_fuzzy_matching()
    DATABASE.execute('INSERT INTO version (version) VALUES (?)', [new_version])
    DATABASE.execute('COMMIT')

def update_fuzzy_matching():
    format_id = get_format_id('Penny Dreadful', True)
    DATABASE.execute('DROP TABLE IF EXISTS fuzzy')
    DATABASE.execute('CREATE VIRTUAL TABLE IF NOT EXISTS fuzzy USING spellfix1')
    sql = """INSERT INTO fuzzy (word, rank)
        SELECT LOWER(name), pd_legal
        FROM ({base_select})
    """.format(base_select=base_select())
    DATABASE.execute(sql)
    sql = """INSERT INTO fuzzy (word, rank)
        SELECT LOWER(f.name), SUM(CASE WHEN cl.format_id = {format_id} THEN 1 ELSE 0 END) > 0
        FROM face AS f
        INNER JOIN card AS c ON f.card_id = c.id
        LEFT OUTER JOIN card_legality AS cl ON cl.card_id = c.id AND cl.format_id = {format_id}
        WHERE LOWER(f.name) NOT IN (SELECT word FROM fuzzy)
        GROUP BY f.id
    """.format(format_id=format_id)
    DATABASE.execute(sql)
    aliases = fetcher.card_aliases()
    for alias, name in aliases:
        DATABASE.execute('INSERT INTO fuzzy (word, soundslike) VALUES (LOWER(?), ?)', [name, alias])

def insert_card(c):
    name = card_name(c)
    try:
        card_id = CARD_IDS[name]
    except KeyError:
        sql = 'INSERT INTO card ('
        sql += ', '.join(name for name, prop in card.card_properties().items() if prop['mtgjson'])
        sql += ') VALUES ('
        sql += ', '.join('?' for name, prop in card.card_properties().items() if prop['mtgjson'])
        sql += ')'
        values = [c.get(database2json(name)) for name, prop in card.card_properties().items() if prop['mtgjson']]
        # database.execute commits after each statement, which we want to avoid while inserting cards
        DATABASE.execute(sql, values)
        card_id = DATABASE.value('SELECT last_insert_rowid()')
        CARD_IDS[name] = card_id
    # mtgjson thinks the text of Jhessian Lookout is NULL not '' but that is clearly wrong.
    if c.get('text', None) is None and c['layout'] in ['normal', 'token', 'double-faced', 'split']:
        c['text'] = ''
    c['nameAscii'] = card.unaccent(c.get('name'))
    c['cardId'] = card_id
    c['position'] = 1 if not c.get('names') else c.get('names', [c.get('name')]).index(c.get('name')) + 1
    sql = 'INSERT INTO face ('
    sql += ', '.join(name for name, prop in card.face_properties().items() if not prop['primary_key'])
    sql += ') VALUES ('
    sql += ', '.join('?' for name, prop in card.face_properties().items() if not prop['primary_key'])
    sql += ')'
    values = [c.get(database2json(name)) for name, prop in card.face_properties().items() if not prop['primary_key']]
    DATABASE.execute(sql, values)
    for color in c.get('colors', []):
        color_id = DATABASE.value('SELECT id FROM color WHERE name = ?', [color])
        DATABASE.execute('INSERT INTO card_color (card_id, color_id) VALUES (?, ?)', [card_id, color_id])
    for symbol in c.get('colorIdentity', []):
        color_id = DATABASE.value('SELECT id FROM color WHERE symbol = ?', [symbol])
        DATABASE.execute('INSERT INTO card_color_identity (card_id, color_id) VALUES (?, ?)', [card_id, color_id])
    for supertype in c.get('supertypes', []):
        DATABASE.execute('INSERT INTO card_supertype (card_id, supertype) VALUES (?, ?)', [card_id, supertype])
    for subtype in c.get('subtypes', []):
        DATABASE.execute('INSERT INTO card_subtype (card_id, subtype) VALUES (?, ?)', [card_id, subtype])
    for info in c.get('legalities', []):
        format_id = get_format_id(info['format'], True)
        DATABASE.execute('INSERT INTO card_legality (card_id, format_id, legality) VALUES (?, ?, ?)', [card_id, format_id, info['legality']])

def insert_set(s) -> None:
    sql = 'INSERT INTO `set` ('
    sql += ', '.join(name for name, prop in card.set_properties().items() if prop['mtgjson'])
    sql += ') VALUES ('
    sql += ', '.join('?' for name, prop in card.set_properties().items() if prop['mtgjson'])
    sql += ')'
    values = [date2int(s.get(database2json(name))) for name, prop in card.set_properties().items() if prop['mtgjson']]
    # database.execute commits after each statement, which we want to
    # avoid while inserting sets
    DATABASE.execute(sql, values)
    set_id = DATABASE.value('SELECT last_insert_rowid()')
    for c in s.get('cards', []):
        card_id = CARD_IDS[card_name(c)]
        sql = 'INSERT INTO printing (card_id, set_id, '
        sql += ', '.join(name for name, prop in card.printing_properties().items() if prop['mtgjson'])
        sql += ') VALUES (?, ?, '
        sql += ', '.join('?' for name, prop in card.printing_properties().items() if prop['mtgjson'])
        sql += ')'
        values = [card_id, set_id] + [c.get(database2json(name)) for name, prop in card.printing_properties().items() if prop['mtgjson']]
        DATABASE.execute(sql, values)

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
        + ' WHERE card_id = ? '
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

def card_name(c):
    if c.get('layout') == 'meld':
        if c.get('name') != c.get('names')[2]:
            return c.get('name')
        else:
            return c.get('names')[0]
    return ' // '.join(c.get('names', [c.get('name')]))

initialize()
