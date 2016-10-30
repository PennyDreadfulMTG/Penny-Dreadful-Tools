import re

from magic import card, database, fetcher, mana
from magic.database import db
from shared import dtutil
from shared.database import sqlescape
from shared.pd_exception import InvalidDataException

CARD_IDS = {}
FORMAT_IDS = {}

def layouts():
    return ['normal', 'meld', 'split', 'phenomenon', 'token', 'vanguard', 'double-faced', 'plane', 'flip', 'scheme', 'leveler']

def initialize():
    current_version = fetcher.mtgjson_version()
    if current_version > database.version():
        print('Database update required')
        update_database(str(current_version))

# 260 makes 'Odds/Ends' match 'Odds // Ends' so that's what we're using for our spellfix1 threshold default.
def search(query, fuzzy_threshold=260):
    query = card.canonicalize(query)
    sql = """
        {base_select}
        HAVING LOWER({name_select}) IN (SELECT word FROM fuzzy WHERE word MATCH ? AND distance <= {fuzzy_threshold})
            OR {name_ascii_select} LIKE ?
            OR SUM(CASE WHEN LOWER(face_name) IN (SELECT word FROM fuzzy WHERE word MATCH ? AND distance <= {fuzzy_threshold}) THEN 1 ELSE 0 END) > 0
        ORDER BY pd_legal DESC, name
    """.format(base_select=base_select(), name_select=card.name_select().format(table='u'), name_ascii_select=card.name_select('name_ascii').format(table='u'), fuzzy_threshold=fuzzy_threshold)
    fuzzy_query = '{query}*'.format(query=query)
    like_query = '%{query}%'.format(query=query)
    rs = db().execute(sql, [fuzzy_query, like_query, fuzzy_query])
    return [card.Card(r) for r in rs]

def valid_name(name):
    if name in CARDS_BY_NAME:
        return name
    else:
        try:
            cards = cards_from_query(name, 20)
            if len(cards) > 1:
                raise InvalidDataException('Found more than one card looking for `{name}`'.format(name=name))
            return cards[0].name
        except IndexError:
            raise InvalidDataException('Did not find any cards looking for `{name}`'.format(name=name))

def load_cards(names=None):
    if names:
        names_clause = 'HAVING LOWER({name_select}) IN ({names})'.format(name_select=card.name_select().format(table='u'), names=', '.join(sqlescape(name).lower() for name in names))
    else:
        names_clause = ''
    sql = """
        {base_select}
        {names_clause}
    """.format(base_select=base_select(), names_clause=names_clause)
    rs = db().execute(sql)
    return [card.Card(r) for r in rs]

# Does not check for 4-ofs nor 1 max restricted, yet.
def legal(cards, format_name='Penny Dreadful'):
    sql = """
        SELECT id
        FROM card
        WHERE id IN ({card_ids})
        AND id NOT IN (SELECT card_id FROM card_legality WHERE format_id = (SELECT id FROM format WHERE name = ?) AND legality <> 'Banned')
        """.format(card_ids=', '.join(c.id for c in cards))
    return len(db().execute(sql, [format_name])) == 0

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
        new_list = [r['name'] for r in db().execute(sql)]
        if len(new_list) == 0:
            new_list = fetcher.legal_cards(force=True)
    format_id = get_format_id('Penny Dreadful')
    db().execute('DELETE FROM card_legality WHERE format_id = ?', [format_id])
    sql = """INSERT INTO card_legality (format_id, card_id, legality)
        SELECT {format_id}, id, 'Legal'
        FROM ({base_select})
        WHERE name IN ({names})
    """.format(format_id=format_id, base_select=base_select(), names=', '.join(sqlescape(name) for name in new_list))
    db().execute(sql)
    # Check we got the right number of legal cards.
    n = db().value('SELECT COUNT(*) FROM card_legality WHERE format_id = ?', [format_id])
    if n != len(new_list):
        print("Found {n} pd legal cards in the database but the list was {len} long".format(n=n, len=len(new_list)))
        sql = 'SELECT name FROM ({base_select}) WHERE id IN (SELECT card_id FROM card_legality WHERE format_id = {format_id})'.format(base_select=base_select(), format_id=format_id)
        db_legal_list = [row['name'] for row in db().execute(sql)]
        print(set(new_list).symmetric_difference(set(db_legal_list)))
    return new_list

def update_database(new_version):
    db().execute('BEGIN TRANSACTION')
    db().execute('DELETE FROM version')
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
    db().execute("UPDATE face SET cmc = 0 WHERE cmc IS NULL AND card_id IN (SELECT id FROM card WHERE layout IN ('normal', 'double-faced', 'flip', 'leveler', 'token', 'split'))")
    rs = db().execute('SELECT id, name FROM rarity')
    for row in rs:
        db().execute('UPDATE printing SET rarity_id = ? WHERE rarity = ?', [row['id'], row['name']])
    update_fuzzy_matching()
    db().execute('INSERT INTO version (version) VALUES (?)', [new_version])
    db().execute('COMMIT')

def update_fuzzy_matching():
    format_id = get_format_id('Penny Dreadful', True)
    db().execute('DROP TABLE IF EXISTS fuzzy')
    db().execute('CREATE VIRTUAL TABLE IF NOT EXISTS fuzzy USING spellfix1')
    sql = """INSERT INTO fuzzy (word, rank)
        SELECT LOWER(name), pd_legal
        FROM ({base_select})
    """.format(base_select=base_select())
    db().execute(sql)
    sql = """INSERT INTO fuzzy (word, rank)
        SELECT LOWER(f.name), SUM(CASE WHEN cl.format_id = {format_id} THEN 1 ELSE 0 END) > 0
        FROM face AS f
        INNER JOIN card AS c ON f.card_id = c.id
        LEFT OUTER JOIN card_legality AS cl ON cl.card_id = c.id AND cl.format_id = {format_id}
        WHERE LOWER(f.name) NOT IN (SELECT word FROM fuzzy)
        GROUP BY f.id
    """.format(format_id=format_id)
    db().execute(sql)
    aliases = fetcher.card_aliases()
    for alias, name in aliases:
        db().execute('INSERT INTO fuzzy (word, soundslike) VALUES (LOWER(?), ?)', [name, alias])

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
        db().execute(sql, values)
        card_id = db().value('SELECT last_insert_rowid()')
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
    db().execute(sql, values)
    for color in c.get('colors', []):
        color_id = db().value('SELECT id FROM color WHERE name = ?', [color])
        db().execute('INSERT INTO card_color (card_id, color_id) VALUES (?, ?)', [card_id, color_id])
    for symbol in c.get('colorIdentity', []):
        color_id = db().value('SELECT id FROM color WHERE symbol = ?', [symbol])
        db().execute('INSERT INTO card_color_identity (card_id, color_id) VALUES (?, ?)', [card_id, color_id])
    for supertype in c.get('supertypes', []):
        db().execute('INSERT INTO card_supertype (card_id, supertype) VALUES (?, ?)', [card_id, supertype])
    for subtype in c.get('subtypes', []):
        db().execute('INSERT INTO card_subtype (card_id, subtype) VALUES (?, ?)', [card_id, subtype])
    for info in c.get('legalities', []):
        format_id = get_format_id(info['format'], True)
        db().execute('INSERT INTO card_legality (card_id, format_id, legality) VALUES (?, ?, ?)', [card_id, format_id, info['legality']])

def insert_set(s) -> None:
    sql = 'INSERT INTO `set` ('
    sql += ', '.join(name for name, prop in card.set_properties().items() if prop['mtgjson'])
    sql += ') VALUES ('
    sql += ', '.join('?' for name, prop in card.set_properties().items() if prop['mtgjson'])
    sql += ')'
    values = [date2int(s.get(database2json(name))) for name, prop in card.set_properties().items() if prop['mtgjson']]
    # database.execute commits after each statement, which we want to
    # avoid while inserting sets
    db().execute(sql, values)
    set_id = db().value('SELECT last_insert_rowid()')
    for c in s.get('cards', []):
        card_id = CARD_IDS[card_name(c)]
        sql = 'INSERT INTO printing (card_id, set_id, '
        sql += ', '.join(name for name, prop in card.printing_properties().items() if prop['mtgjson'])
        sql += ') VALUES (?, ?, '
        sql += ', '.join('?' for name, prop in card.printing_properties().items() if prop['mtgjson'])
        sql += ')'
        values = [card_id, set_id] + [c.get(database2json(name)) for name, prop in card.printing_properties().items() if prop['mtgjson']]
        db().execute(sql, values)

def get_format_id(name, allow_create=False):
    if len(FORMAT_IDS) == 0:
        rs = db().execute('SELECT id, name FROM format')
        for row in rs:
            FORMAT_IDS[row['name']] = row['id']
    if name not in FORMAT_IDS.keys() and allow_create:
        db().execute('INSERT INTO format (name) VALUES (?)', [name])
        FORMAT_IDS[name] = db().value('SELECT last_insert_rowid()')
    if name not in FORMAT_IDS.keys():
        return None
    return FORMAT_IDS[name]

def check_layouts():
    rs = db().execute('SELECT DISTINCT layout FROM card')
    if sorted([row['layout'] for row in rs]) != sorted(layouts()):
        print('WARNING. There has been a change in layouts. The update to 0 CMC may no longer be valid.')

def get_printings(generalized_card: card.Card):
    sql = 'SELECT ' + (', '.join(property for property in card.printing_properties())) \
        + ' FROM printing ' \
        + ' WHERE card_id = ? '
    rs = db().execute(sql, [generalized_card.id])
    return [card.Printing(r) for r in rs]

def database2json(propname: str) -> str:
    if propname == "system_id":
        propname = "id"
    return underscore2camel(propname)

def underscore2camel(s):
    return re.sub(r'(?!^)_([a-zA-Z])', lambda m: m.group(1).upper(), s)

def date2int(s):
    return dtutil.parse(s, '%Y-%m-%d', dtuil.WOTC_TZ)

def card_name(c):
    if c.get('layout') == 'meld':
        if c.get('name') != c.get('names')[2]:
            return c.get('name')
        else:
            return c.get('names')[0]
    return ' // '.join(c.get('names', [c.get('name')]))

def deck_sort(c):
    s = ''
    if c.is_creature():
        s += 'A'
    elif c.is_land():
        s += 'C'
    else:
        s += 'B'
    if c.mana_cost and mana.variable(c.mana_cost):
        s += 'X'
    else:
        s += 'A'
    s += str(c.cmc).zfill(10)
    s += c.name
    return s

def cards_from_query(query, fuzziness_threshold=260):
    # Skip searching if the request is too short.
    if len(query) <= 2:
        return []

    query = card.canonicalize(query)

    # If we searched for an alias, change query so we can find the card in the results.
    for alias, name in fetcher.card_aliases():
        if query == card.canonicalize(alias):
            query = card.canonicalize(name)

    cards = search(query, fuzziness_threshold)
    cards = [c for c in cards if c.layout != 'token' and c.type != 'Vanguard']

    # First look for an exact match.
    results = []
    for c in cards:
        names = [card.canonicalize(name) for name in c.names]
        if query in names:
            results.append(c)
    if len(results) > 0:
        return results


    # If not found, use cards that start with the query and a punctuation char.
    for c in cards:
        names = [card.canonicalize(name) for name in c.names]
        for name in names:
            if name.startswith('{query} '.format(query=query)) or name.startswith('{query},'.format(query=query)):
                results.append(c)
    if len(results) > 0:
        return results

    # If not found, use cards that start with the query.
    for c in cards:
        names = [card.canonicalize(name) for name in c.names]
        for name in names:
            if name.startswith(query):
                results.append(c)
    if len(results) > 0:
        return results

    # If we didn't find any of those then use all search results.
    return cards

initialize()
CARDS_BY_NAME = {c.name: c for c in load_cards()}
