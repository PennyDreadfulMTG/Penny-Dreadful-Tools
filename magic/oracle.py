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
        {base_query}
        HAVING LOWER({name_query}) IN (SELECT word FROM fuzzy WHERE word MATCH ? AND distance <= {fuzzy_threshold})
            OR {namename_ascii_query} LIKE ?
            OR SUM(CASE WHEN LOWER(face_name) IN (SELECT word FROM fuzzy WHERE word MATCH ? AND distance <= {fuzzy_threshold}) THEN 1 ELSE 0 END) > 0
        ORDER BY pd_legal DESC, name
    """.format(base_query=base_query(), name_query=card.name_query().format(table='u'), namename_ascii_query=card.name_query('name_ascii').format(table='u'), fuzzy_threshold=fuzzy_threshold)
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
        names_clause = 'HAVING LOWER({name_query}) IN ({names})'.format(name_query=card.name_query().format(table='u'), names=', '.join(sqlescape(name).lower() for name in names))
    else:
        names_clause = ''
    sql = """
        {base_query}
        {names_clause}
    """.format(base_query=base_query(), names_clause=names_clause)
    rs = db().execute(sql)
    return [card.Card(r) for r in rs]

# Does not check for 4-ofs nor 1 max restricted, yet.
def legal_deck(cards):
    cs = legal_cards()
    return len([c for c in cards if c.name not in cs]) == 0

def legality(cards):
    l = {}
    cs = legal_cards()
    for c in cards:
        l[c.id] = c.name in cs
    return l

def base_query(where_clause='(1 = 1)'):
    return """
        SELECT
            {card_queries},
            {face_queries},
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
        card_queries=', '.join(prop['query'].format(table='u', column=name) for name, prop in card.card_properties().items()),
        face_queries=', '.join(prop['query'].format(table='u', column=name) for name, prop in card.face_properties().items()),
        format_id=get_format_id('Penny Dreadful'),
        card_props=', '.join('c.{name}'.format(name=name) for name in card.card_properties()),
        face_props=', '.join('f.{name}'.format(name=name) for name in card.face_properties() if name not in ['id', 'name']),
        where_clause=where_clause)

def legal_cards(force=False):
    if len(LEGAL_CARDS) == 0 or force:
        set_legal_cards(force)
    return LEGAL_CARDS

def set_legal_cards(force=False, season=None):
    new_list = ['']
    try:
        new_list = fetcher.legal_cards(force, season)
    except fetcher.FetchException:
        pass
    # This was a workaround when fetcher didn't store content.  It's never going to trigger anymore.
    # if new_list == ['']:
    #     sql = '{base_query} HAVING pd_legal = 1'.format(base_query=base_query())
    #     new_list = [r['name'] for r in db().execute(sql)]
    #     if len(new_list) == 0:
    #         new_list = fetcher.legal_cards(force=True)
    if season is None:
        format_id = get_format_id('Penny Dreadful')
    else:
        format_id = get_format_id('Penny Dreadful {season}'.format(season=season), True)
    db().execute('DELETE FROM card_legality WHERE format_id = ?', [format_id])
    sql = """INSERT INTO card_legality (format_id, card_id, legality)
        SELECT {format_id}, id, 'Legal'
        FROM ({base_query})
        WHERE name IN ({names})
    """.format(format_id=format_id, base_query=base_query(), names=', '.join(sqlescape(name) for name in new_list))
    db().execute(sql)
    # Check we got the right number of legal cards.
    n = db().value('SELECT COUNT(*) FROM card_legality WHERE format_id = ?', [format_id])
    if n != len(new_list):
        print("Found {n} pd legal cards in the database but the list was {len} long".format(n=n, len=len(new_list)))
        sql = 'SELECT name FROM ({base_query}) WHERE id IN (SELECT card_id FROM card_legality WHERE format_id = {format_id})'.format(base_query=base_query(), format_id=format_id)
        db_legal_list = [row['name'] for row in db().execute(sql)]
        print(set(new_list).symmetric_difference(set(db_legal_list)))
    LEGAL_CARDS.clear()
    for name in new_list:
        LEGAL_CARDS.append(name)

def update_database(new_version):
    db().execute('BEGIN TRANSACTION')
    db().execute('DELETE FROM version')
    cards = fetcher.all_cards()
    cards = fake_flip_cards(cards)
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
        FROM ({base_query})
    """.format(base_query=base_query())
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
    values = [date2int(s.get(database2json(name)), name) for name, prop in card.set_properties().items() if prop['mtgjson']]
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

def date2int(s, name):
    if name == 'release_date':
        return dtutil.parse_to_ts(s, '%Y-%m-%d', dtutil.WOTC_TZ)
    return s

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

# Workaround mtgjson bug until they fix it by hardcoding the missing flip cards that we care about.
def fake_flip_cards(cards):
    cards['Student of Elements'] = {
        'text': 'When Student of Elements has flying, flip it.',
        'manaCost': '{1}{U}',
        'type': 'Creature — Human Wizard',
        'power': '1',
        'layout': 'flip',
        'names': ['Student of Elements', 'Tobita, Master of Winds'],
        'types': ['Creature'],
        'colorIdentity': ['U'],
        'toughness': '1',
        'cmc': 2,
        'imageName': 'student of elements',
        'legalities': [
            {'format': 'Commander', 'legality': 'Legal'},
            {'format': 'Kamigawa Block', 'legality': 'Legal'},
            {'format': 'Legacy', 'legality': 'Legal'},
            {'format': 'Modern', 'legality': 'Legal'},
            {'format': 'Vintage', 'legality': 'Legal'}],
        'name': 'Student of Elements',
        'subtypes': ['Human', 'Wizard'],
        'printings': ['COK'],
        'colors': ['Blue']
    }
    cards['Cunning Bandit'] = {
        'text': 'Whenever you cast a Spirit or Arcane spell, you may put a ki counter on Cunning Bandit.\nAt the beginning of the end step, if there are two or more ki counters on Cunning Bandit, you may flip it.',
        'manaCost': '{1}{R}{R}',
        'type': 'Creature — Human Warrior',
        'power': '2',
        'layout': 'flip',
        'names': ['Cunning Bandit', 'Azamuki, Treachery Incarnate'],
        'types': ['Creature'],
        'colorIdentity': ['R'],
        'toughness': '2',
        'cmc': 3,
        'imageName': 'cunning bandit',
        'legalities': [
            {'format': 'Commander', 'legality': 'Legal'},
            {'format': 'Kamigawa Block', 'legality': 'Legal'},
            {'format': 'Legacy', 'legality': 'Legal'},
            {'format': 'Modern', 'legality': 'Legal'},
            {'format': 'Vintage', 'legality': 'Legal'}],
        'name': 'Cunning Bandit',
        'subtypes': ['Human', 'Warrior'],
        'printings': ['BOK'],
        'colors': ['Red']
    }
    cards['Nezumi Graverobber'] = {
        'text': '{1}{B}: Exile target card from an opponent\'s graveyard. If no cards are in that graveyard, flip Nezumi Graverobber.',
        'manaCost': '{1}{B}',
        'type': 'Creature — Rat Rogue',
        'power': '2',
        'layout': 'flip',
        'names': ['Nezumi Graverobber', 'Nighteyes the Desecrator'],
        'types': ['Creature'],
        'colorIdentity': ['B'],
        'toughness': '1',
        'cmc': 2,
        'imageName': 'nezumi graverobber',
        'legalities': [
            {'format': 'Commander', 'legality': 'Legal'},
            {'format': 'Kamigawa Block', 'legality': 'Legal'},
            {'format': 'Legacy', 'legality': 'Legal'},
            {'format': 'Modern', 'legality': 'Legal'},
            {'format': 'Vintage', 'legality': 'Legal'}],
        'name': 'Nezumi Graverobber',
        'subtypes': ['Rat', 'Rogue'],
        'printings': ['COK'], # Also Commander
        'colors': ['Black']
    }
    cards['Hired Muscle'] = {
        'text': 'Whenever you cast a Spirit or Arcane spell, you may put a ki counter on Hired Muscle.\nAt the beginning of the end step, if there are two or more ki counters on Hired Muscle, you may flip it.',
        'manaCost': '{1}{B}{B}',
        'type': 'Creature — Human Warrior',
        'power': '2',
        'layout': 'flip',
        'names': ['Hired Muscle', 'Scarmaker'],
        'types': ['Creature'],
        'colorIdentity': ['B'],
        'toughness': '2',
        'cmc': 3,
        'imageName': 'hired muscle',
        'legalities': [
            {'format': 'Commander', 'legality': 'Legal'},
            {'format': 'Kamigawa Block', 'legality': 'Legal'},
            {'format': 'Legacy', 'legality': 'Legal'},
            {'format': 'Modern', 'legality': 'Legal'},
            {'format': 'Vintage', 'legality': 'Legal'}],
        'name': 'Hired Muscle',
        'subtypes': ['Human', 'Warrior'],
        'printings': ['BOK'],
        'colors': ['Black']
    }
    cards['Orochi Eggwatcher'] = {
        'text': '{2}{G}, {T}: Put a 1/1 green Snake creature token onto the battlefield. If you control ten or more creatures, flip Orochi Eggwatcher.',
        'manaCost': '{2}{G}',
        'type': 'Creature — Snake Shaman',
        'power': '1',
        'layout': 'flip',
        'names': ['Orochi Eggwatcher', 'Shidako, Broodmistress'],
        'types': ['Creature'],
        'colorIdentity': ['G'],
        'toughness': '1',
        'cmc': 3,
        'imageName': 'orochi eggwatcher',
        'legalities': [
            {'format': 'Commander', 'legality': 'Legal'},
            {'format': 'Kamigawa Block', 'legality': 'Legal'},
            {'format': 'Legacy', 'legality': 'Legal'},
            {'format': 'Modern', 'legality': 'Legal'},
            {'format': 'Vintage', 'legality': 'Legal'}],
        'name': 'Orochi Eggwatcher',
        'subtypes': ['Snake', 'Shaman'],
        'printings': ['COK'],
        'colors': ['Green']
    }
    cards['Kitsune Mystic'] = {
        'text': 'At the beginning of the end step, if Kitsune Mystic is enchanted by two or more Auras, flip it.',
        'manaCost': '{3}{W}',
        'type': 'Creature — Fox Wizard',
        'power': '2',
        'layout': 'flip',
        'names': ['Kitsune Mystic', 'Autumn-Tail, Kitsune Sage'],
        'types': ['Creature'],
        'colorIdentity': ['W'],
        'toughness': '3',
        'cmc': 4,
        'imageName': 'kitsune mystic',
        'legalities': [
            {'format': 'Commander', 'legality': 'Legal'},
            {'format': 'Kamigawa Block', 'legality': 'Legal'},
            {'format': 'Legacy', 'legality': 'Legal'},
            {'format': 'Modern', 'legality': 'Legal'},
            {'format': 'Vintage', 'legality': 'Legal'}],
        'name': 'Kitsune Mystic',
        'subtypes': ['Fox', 'Wizard'],
        'printings': ['COK'],
        'colors': ['White']
    }
    cards['Bushi Tenderfoot'] = {
        'text': 'When a creature dealt damage by Bushi Tenderfoot this turn dies, flip Bushi Tenderfoot.',
        'manaCost': '{W}',
        'type': 'Creature — Human Soldier',
        'power': '1',
        'layout': 'flip',
        'names': ['Bushi Tenderfoot', 'Kenzo the Hardhearted'],
        'types': ['Creature'],
        'colorIdentity': ['W'],
        'toughness': '1',
        'cmc': 1,
        'imageName': 'bushi tenderfoot',
        'legalities': [
            {'format': 'Commander', 'legality': 'Legal'},
            {'format': 'Kamigawa Block', 'legality': 'Legal'},
            {'format': 'Legacy', 'legality': 'Legal'},
            {'format': 'Modern', 'legality': 'Legal'},
            {'format': 'Vintage', 'legality': 'Legal'}],
        'name': 'Bushi Tenderfoot',
        'subtypes': ['Human', 'Soldier'],
        'printings': ['COK'],
        'colors': ['White']
    }
    cards['Faithful Squire'] = {
        'text': 'Whenever you cast a Spirit or Arcane spell, you may put a ki counter on Faithful Squire.\nAt the beginning of the end step, if there are two or more ki counters on Faithful Squire, you may flip it.',
        'manaCost': '{1}{W}{W}',
        'type': 'Creature — Human Soldier',
        'power': '2',
        'layout': 'flip',
        'names': ['Faithful Squire', 'Kaiso, Memory of Loyalty'],
        'types': ['Creature'],
        'colorIdentity': ['W'],
        'toughness': '2',
        'cmc': 3,
        'imageName': 'faithful squire',
        'legalities': [
            {'format': 'Commander', 'legality': 'Legal'},
            {'format': 'Kamigawa Block', 'legality': 'Legal'},
            {'format': 'Legacy', 'legality': 'Legal'},
            {'format': 'Modern', 'legality': 'Legal'},
            {'format': 'Vintage', 'legality': 'Legal'}],
        'name': 'Faithful Squire',
        'subtypes': ['Human', 'Soldier'],
        'printings': ['BOK'],
        'colors': ['White']
    }
    cards['Initiate of Blood'] = {
        'text': '{T}: Initiate of Blood deals 1 damage to target creature that was dealt damage this turn. When that creature dies this turn, flip Initiate of Blood.',
        'manaCost': '{3}{R}',
        'type': 'Creature — Ogre Shaman',
        'power': '2',
        'layout': 'flip',
        'names': ['Initiate of Blood', 'Goka the Unjust'],
        'types': ['Creature'],
        'colorIdentity': ['R'],
        'toughness': '2',
        'cmc': 4,
        'imageName': 'intitiate of blood',
        'legalities': [
            {'format': 'Commander', 'legality': 'Legal'},
            {'format': 'Kamigawa Block', 'legality': 'Legal'},
            {'format': 'Legacy', 'legality': 'Legal'},
            {'format': 'Modern', 'legality': 'Legal'},
            {'format': 'Vintage', 'legality': 'Legal'}],
        'name': 'Initiate of Blood',
        'subtypes': ['Ogre', 'Shaman'],
        'printings': ['COK'],
        'colors': ['Red']
    }
    return cards

LEGAL_CARDS = []
initialize()
CARDS_BY_NAME = {c.name: c for c in load_cards()}
