import re

from magic import card, database, fetcher
from magic.database import db
from shared import dtutil
from shared.database import sqlescape

FORMAT_IDS = {}
CARD_IDS = {}

def init():
    current_version = fetcher.mtgjson_version()
    if current_version > database.version():
        print('Database update required')
        update_database(str(current_version))
    set_legal_cards()
    # Don't hardcode this!
    set_legal_cards(season='EMN')
    update_bugged_cards()

def layouts():
    return ['normal', 'meld', 'split', 'phenomenon', 'token', 'vanguard', 'double-faced', 'plane', 'flip', 'scheme', 'leveler']

def base_query(where_clause='(1 = 1)'):
    return """
        SELECT
            {card_queries},
            {face_queries},
            GROUP_CONCAT(face_name, '|') AS names,
            legalities,
            pd_legal,
            bug_desc
            FROM
                (SELECT {card_props}, {face_props}, f.name AS face_name,
                SUM(CASE WHEN cl.format_id = {format_id} THEN 1 ELSE 0 END) > 0 AS pd_legal,
                GROUP_CONCAT(fo.name || ':' || cl.legality) AS legalities, 
                bugs.description AS bug_desc
                FROM card AS c
                INNER JOIN face AS f ON c.id = f.card_id
                LEFT OUTER JOIN card_legality AS cl ON c.id = cl.card_id
                INNER JOIN format AS fo ON cl.format_id = fo.id
                LEFT OUTER JOIN card_bugs AS bugs ON c.id = bugs.card_id
                GROUP BY f.id
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


def update_database(new_version):
    db().execute('BEGIN TRANSACTION')
    db().execute('DELETE FROM version')
    db().execute("""
    DELETE FROM card;
    DELETE FROM card_alias;
    DELETE FROM card_color;
    DELETE FROM card_color_identity;
    DELETE FROM card_legality;
    DELETE FROM card_subtype;
    DELETE FROM card_supertype;
    DELETE FROM card_type;
    DELETE FROM face;
    DELETE FROM printing;
    DELETE FROM `set`;
    """)
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
    update_bugged_cards()
    db().execute('INSERT INTO version (version) VALUES (?)', [new_version])
    db().execute('COMMIT')

def check_layouts():
    rs = db().execute('SELECT DISTINCT layout FROM card')
    if sorted([row['layout'] for row in rs]) != sorted(layouts()):
        print('WARNING. There has been a change in layouts. The update to 0 CMC may no longer be valid.')

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

def update_bugged_cards():
    # This may or may not be within a TRANSACTION. Use a SAVEPOINT.
    db().execute("SAVEPOINT bugs")
    db().execute("DELETE FROM card_bugs")
    for name, bug, _, __ in fetcher.bugged_cards():
        card_id = db().value("SELECT card_id FROM face WHERE name = ?", [name])
        if card_id is None:
            print("UNKNOWN BUGGED CARD: {card}".format(card=name))
            continue
        db().execute("INSERT INTO card_bugs (card_id, description) VALUES (?, ?)", [card_id, bug])
    db().execute("RELEASE bugs")

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

def set_legal_cards(force=False, season=None):
    new_list = ['']
    try:
        new_list = fetcher.legal_cards(force, season)
    except fetcher.FetchException:
        pass
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
    return new_list

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

# I'm not sure this belong here, but it's here for now.
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

def card_name(c):
    if c.get('layout') == 'meld':
        if c.get('name') != c.get('names')[2]:
            return c.get('name')
        else:
            return c.get('names')[0]
    return ' // '.join(c.get('names', [c.get('name')]))

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
    cards['Akki Lavarunner'] = {
        'text': 'Haste\nWhenever Akki Lavarunner deals damage to an opponent, flip it.',
        'manaCost': '{3}{R}',
        'type': 'Creature — Goblin Warrior',
        'power': '1',
        'layout': 'flip',
        'names': ['Akki Lavarunner', 'Tok-Tok, Volcano Born'],
        'types': ['Creature'],
        'colorIdentity': ['R'],
        'toughness': '1',
        'cmc': 4,
        'imageName': 'akki lavarunner',
        'legalities': [
            {'format': 'Commander', 'legality': 'Legal'},
            {'format': 'Kamigawa Block', 'legality': 'Legal'},
            {'format': 'Legacy', 'legality': 'Legal'},
            {'format': 'Modern', 'legality': 'Legal'},
            {'format': 'Vintage', 'legality': 'Legal'}],
        'name': 'Akki Lavarunner',
        'subtypes': ['Ogre', 'Shaman'],
        'printings': ['COK'],
        'colors': ['Red']
    }
    cards["Budoka Gardener"] = {
        "text": "{T}: You may put a land card from your hand onto the battlefield. If you control ten or more lands, flip Budoka Gardener.",
        "manacost": "{1}{G}",
        "type": "Creature — Human Monk",
        "power": "2",
        "layout": "flip",
        "names": ["Budoka Gardener", "Dokai, Weaver of Life"],
        "types": ["Creature"],
        'colorIdentity': ['G'],
        "toughness": "1",
        "cmc": 2,
        'imageName': 'budoka gardener',
        "legalities": [
            {"format": "Modern", "legality": "Legal"},
            {"format": "Kamigawa Block", "legality": "Legal"},
            {"format": "Legacy", "legality": "Legal"},
            {"format": "Vintage", "legality": "Legal"},
            {"format": "Commander", "legality": "Legal"}],
        "name": "Budoka Gardener",
        "subTypes": ["Human", "Monk"],
        "printings": ["CHK"],
        "colors": ["Green"],
        "rarity": "Rare"
    }
    return cards
