import re
from typing import Dict

import pkg_resources

from magic import card, database, fetcher, rotation
from magic.database import db
from shared import dtutil
from shared.database import sqlescape
from shared.pd_exception import InvalidDataException
from shared.whoosh_write import WhooshWriter

# Database setup for the magic package. Mostly internal. To interface with what the package knows about magic cards use the `oracle` module.

FORMAT_IDS: Dict[str, int] = {}
CARD_IDS: Dict[str, int] = {}

SEASONS = ['EMN', 'KLD', 'AER', 'AKH', 'HOU', 'XLN', 'RIX', 'DOM']

HARDCODED_MELD_NAMES = [
    ["Gisela, the Broken Blade", "Bruna, the Fading Light", "Brisela, Voice of Nightmares"],
    ["Graf Rats", "Midnight Scavengers", "Chittering Host"],
    ["Hanweir Garrison", "Hanweir Battlements", "Hanweir, the Writhing Township"]
]

HARDCODED_DFC_NAMES = {
    'Mayor of Avabruck': ['Mayor of Avabruck', 'Howlpack Alpha'],
    'Ravenous Demon': ['Ravenous Demon', 'Archdemon of Greed'],
    'Mondronen Shaman': ['Mondronen Shaman', 'Tovolar\'s Magehunter'],
    'Ludevic\'s Test Subject': ['Ludevic\'s Test Subject', 'Ludevic\'s Abomination'],
    'Civilized Scholar': ['Civilized Scholar', 'Homicidal Brute'],
    'Thraben Sentry': ['Thraben Sentry', 'Thraben Militia'],
    'Daybreak Ranger': ['Daybreak Ranger', 'Nightfall Predator'],
    'Village Ironsmith': ['Village Ironsmith', 'Ironfang'],
    'Tormented Pariah': ['Tormented Pariah', 'Rampaging Werewolf'],
    'Villagers of Estwald': ['Villagers of Estwald', 'Howlpack of Estwald'],
    'Grizzled Outcasts': ['Grizzled Outcasts', 'Krallenhorde Wantons'],
    'Gatstaf Shepherd': ['Gatstaf Shepherd', 'Gatstaf Howler'],
    'Hinterland Hermit': ['Hinterland Hermit', 'Hinterland Scourge'],
    'Chalice of Life': ['Chalice of Life', 'Chalice of Death'],
    'Scorned Villager': ['Scorned Villager', 'Moonscarred Werewolf'],
    'Lambholt Elder': ['Lambholt Elder', 'Silverpelt Werewolf'],
    'Nissa, Vastwood Seer': ['Nissa, Vastwood Seer', 'Nissa, Sage Animist'],
    'Elbrus, the Binding Blade': ['Elbrus, the Binding Blade', 'Withengar Unbound'],
    'Huntmaster of the Fells': ['Huntmaster of the Fells', 'Ravager of the Fells'],

    'Howlpack Alpha': ['Mayor of Avabruck', 'Howlpack Alpha'],
    'Archdemon of Greed': ['Ravenous Demon', 'Archdemon of Greed'],
    'Tovolar\'s Magehunter': ['Mondronen Shaman', 'Tovolar\'s Magehunter'],
    'Ludevic\'s Abomination': ['Ludevic\'s Test Subject', 'Ludevic\'s Abomination'],
    'Homicidal Brute': ['Civilized Scholar', 'Homicidal Brute'],
    'Thraben Militia': ['Thraben Sentry', 'Thraben Militia'],
    'Nightfall Predator': ['Daybreak Ranger', 'Nightfall Predator'],
    'Ironfang': ['Village Ironsmith', 'Ironfang'],
    'Rampaging Werewolf': ['Tormented Pariah', 'Rampaging Werewolf'],
    'Howlpack of Estwald': ['Villagers of Estwald', 'Howlpack of Estwald'],
    'Krallenhorde Wantons': ['Grizzled Outcasts', 'Krallenhorde Wantons'],
    'Gatstaf Howler': ['Gatstaf Shepherd', 'Gatstaf Howler'],
    'Hinterland Scourge': ['Hinterland Hermit', 'Hinterland Scourge'],
    'Chalice of Death': ['Chalice of Life', 'Chalice of Death'],
    'Moonscarred Werewolf': ['Scorned Villager', 'Moonscarred Werewolf'],
    'Silverpelt Werewolf': ['Lambholt Elder', 'Silverpelt Werewolf'],
    'Nissa, Sage Animist': ['Nissa, Vastwood Seer', 'Nissa, Sage Animist'],
    'Withengar Unbound': ['Elbrus, the Binding Blade', 'Withengar Unbound'],
    'Ravager of the Fells': ['Huntmaster of the Fells', 'Ravager of the Fells']
}

def init():
    current_version = fetcher.mtgjson_version()
    if pkg_resources.parse_version(current_version) > pkg_resources.parse_version(database.mtgjson_version()):
        print('Database update required')
        update_database(current_version)
        set_legal_cards()
        update_cache()
        reindex()

def layouts():
    return {'normal': True, 'meld': True, 'split': True, 'phenomenon': False, 'token': False, 'vanguard': False, 'double-faced': True, 'plane': False, 'flip': True, 'scheme': False, 'leveler': True, 'aftermath': True}

def cached_base_query(where='(1 = 1)'):
    return 'SELECT * FROM _cache_card AS c WHERE {where}'.format(where=where)

def base_query(where='(1 = 1)'):
    return """
        SELECT
            {card_queries},
            {face_queries},
            GROUP_CONCAT(face_name SEPARATOR '|') AS names,
            legalities,
            pd_legal,
            bugs
            FROM (
                SELECT {card_props}, {face_props}, f.name AS face_name,
                    pd_legal,
                    legalities
                FROM
                    card AS c
                INNER JOIN
                    face AS f ON c.id = f.card_id
                LEFT JOIN (
                    SELECT
                        cl.card_id,
                        SUM(CASE WHEN cl.format_id = {format_id} THEN 1 ELSE 0 END) > 0 AS pd_legal,
                        GROUP_CONCAT({legality_code}) AS legalities
                    FROM
                        card_legality AS cl
                    LEFT JOIN
                        format AS fo ON cl.format_id = fo.id
                    GROUP BY
                        cl.card_id
                ) AS cl ON cl.card_id = c.id
                GROUP BY
                    f.id
                ORDER BY
                    f.card_id, f.position
            ) AS u
            LEFT JOIN (
                SELECT
                    cb.card_id,
                    GROUP_CONCAT({bug_repr} SEPARATOR '_SEPARATOR_') AS bugs
                FROM
                    card_bug AS cb
                GROUP BY
                    cb.card_id
            ) AS bugs ON u.id = bugs.card_id
            WHERE u.id IN (SELECT c.id FROM card AS c INNER JOIN face AS f ON c.id = f.card_id WHERE {where})
            GROUP BY u.id
    """.format(
        card_queries=', '.join(prop['query'].format(table='u', column=name) for name, prop in card.card_properties().items()),
        face_queries=', '.join(prop['query'].format(table='u', column=name) for name, prop in card.face_properties().items()),
        bug_repr=db().concat(['cb.description', "'|'", 'cb.classification', "'|'", 'cb.last_confirmed', "'|'", 'cb.url', "'|'", 'cb.from_bug_blog']),
        format_id=get_format_id('Penny Dreadful'),
        legality_code=db().concat(['fo.name', "':'", 'cl.legality']),
        card_props=', '.join('c.{name}'.format(name=name) for name in card.card_properties()),
        face_props=', '.join('f.{name}'.format(name=name) for name in card.face_properties() if name not in ['id', 'name']),
        where=where)


def update_database(new_version):
    db().begin()
    db().execute('DELETE FROM version')
    db().execute("""
    DELETE FROM card_alias;
    DELETE FROM card_color;
    DELETE FROM card_color_identity;
    DELETE FROM card_legality;
    DELETE FROM card_subtype;
    DELETE FROM card_supertype;
    DELETE FROM card_type;
    DELETE FROM card_bug;
    DELETE FROM face;
    DELETE FROM printing;
    DELETE FROM card;
    DELETE FROM `set`;
    """)
    cards = fetcher.all_cards()
    cards = add_hardcoded_cards(cards)
    melded_faces = []
    for _, c in cards.items():
        if c.get('layout') == 'meld' and c.get('name') == c.get('names')[2]:
            melded_faces.append(c)
        else:
            insert_card(c, update_index=False)
    for face in melded_faces:
        insert_card(face, update_index=False)
        first, second = face['names'][0:2]
        face['names'][0] = second
        face['names'][1] = first
        insert_card(face, update_index=False)
    sets = fetcher.all_sets()
    for _, s in sets.items():
        insert_set(s)
    check_layouts() # Check that the hardcoded list of layouts we're about to use is still valid.
    rs = db().execute('SELECT id, name FROM rarity')
    for row in rs:
        db().execute('UPDATE printing SET rarity_id = ? WHERE rarity = ?', [row['id'], row['name']])
    update_fuzzy_matching()
    update_bugged_cards(False)
    update_pd_legality()
    db().execute('INSERT INTO version (version) VALUES (?)', [new_version])
    db().commit()

def check_layouts():
    rs = db().execute('SELECT DISTINCT layout FROM card')
    if sorted([row['layout'] for row in rs]) != sorted(layouts().keys()):
        print('WARNING. There has been a change in layouts. The update to 0 CMC may no longer be valid. You may also want to add it to playable_layouts. Comparing {old} with {new}.'.format(old=sorted(layouts().keys()), new=sorted([row['layout'] for row in rs])))

def update_fuzzy_matching():
    format_id = get_format_id('Penny Dreadful', True)
    if db().is_sqlite():
        db().execute('DROP TABLE IF EXISTS fuzzy')
        db().execute('CREATE VIRTUAL TABLE IF NOT EXISTS fuzzy USING spellfix1')
        sql = """INSERT INTO fuzzy (word, rank)
            SELECT LOWER(bq.name), bq.pd_legal
            FROM ({base_query}) AS bq
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

def update_bugged_cards(use_transaction=True):
    bugs = fetcher.bugged_cards()
    if bugs is None:
        return
    if use_transaction:
        db().begin()
    db().execute("DELETE FROM card_bug")
    for bug in bugs:
        last_confirmed_ts = dtutil.parse_to_ts(bug['last_updated'], '%Y-%m-%d %H:%M:%S', dtutil.UTC_TZ)
        card_id = db().value("SELECT card_id FROM face WHERE name = ?", [bug['card']])
        if card_id is None:
            print("UNKNOWN BUGGED CARD: {card}".format(card=bug['card']))
            continue
        db().execute("INSERT INTO card_bug (card_id, description, classification, last_confirmed, url, from_bug_blog) VALUES (?, ?, ?, ?, ?, ?)", [card_id, bug['description'], bug['category'], last_confirmed_ts, bug['url'], bug['bug_blog']])
    if use_transaction:
        db().commit()

def update_pd_legality():
    for s in SEASONS:
        if s == rotation.last_rotation_ex()['code']:
            break
        set_legal_cards(season=s)

def insert_card(c, update_index=True):
    name, card_id = try_find_card_id(c)
    if card_id is None:
        sql = 'INSERT INTO card ('
        sql += ', '.join(name for name, prop in card.card_properties().items() if prop['mtgjson'])
        sql += ') VALUES ('
        sql += ', '.join('?' for name, prop in card.card_properties().items() if prop['mtgjson'])
        sql += ')'
        values = [c.get(database2json(name)) for name, prop in card.card_properties().items() if prop['mtgjson']]
        db().execute(sql, values)
        card_id = db().last_insert_rowid()
        CARD_IDS[name] = card_id
    # mtgjson thinks the text of Jhessian Lookout is NULL not '' but that is clearly wrong.
    if c.get('text', None) is None and c['layout'] in playable_layouts():
        c['text'] = ''
    c['nameAscii'] = card.unaccent(c.get('name'))
    c['searchText'] = re.sub(r'\([^\)]+\)', '', c['text'])
    c['cardId'] = card_id
    c['position'] = 1 if not c.get('names') else c.get('names', [c.get('name')]).index(c.get('name')) + 1
    sql = 'INSERT INTO face ('
    sql += ', '.join(name for name, prop in card.face_properties().items() if not prop['primary_key'])
    sql += ') VALUES ('
    sql += ', '.join('?' for name, prop in card.face_properties().items() if not prop['primary_key'])
    sql += ')'
    values = [c.get(database2json(name)) for name, prop in card.face_properties().items() if not prop['primary_key']]
    try:
        db().execute(sql, values)
    except database.DatabaseException:
        print(c)
        raise
    for color in c.get('colors', []):
        color_id = db().value('SELECT id FROM color WHERE name = ?', [color])
        # INSERT IGNORE INTO because some cards have multiple faces with the same color. See DFCs and What // When // Where // Who // Why.
        db().execute('INSERT IGNORE INTO card_color (card_id, color_id) VALUES (?, ?)', [card_id, color_id])
    for symbol in c.get('colorIdentity', []):
        color_id = db().value('SELECT id FROM color WHERE symbol = ?', [symbol])
        # INSERT IGNORE INTO because some cards have multiple faces with the same color identity. See DFCs and What // When // Where // Who // Why.
        db().execute('INSERT IGNORE INTO card_color_identity (card_id, color_id) VALUES (?, ?)', [card_id, color_id])
    for supertype in c.get('supertypes', []):
        db().execute('INSERT INTO card_supertype (card_id, supertype) VALUES (?, ?)', [card_id, supertype])
    for subtype in c.get('subtypes', []):
        db().execute('INSERT INTO card_subtype (card_id, subtype) VALUES (?, ?)', [card_id, subtype])
    for info in c.get('legalities', []):
        format_id = get_format_id(info['format'], True)
        db().execute('INSERT INTO card_legality (card_id, format_id, legality) VALUES (?, ?, ?)', [card_id, format_id, info['legality']])
    if update_index:
        writer = WhooshWriter()
        c['id'] = c['cardId']
        writer.update_card(c)

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
    set_id = db().last_insert_rowid()
    set_cards = s.get('cards', [])
    fix_mtgjson_melded_cards_array(set_cards)
    fix_double_faced_bug_array(set_cards)
    for c in set_cards:
        _, card_id = try_find_card_id(c)
        if card_id is None:
            raise InvalidDataException("Can't find id for: '{n}': {ns}".format(n=c['name'], ns=c['names']))
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

    if new_list == [''] or new_list is None:
        return None
    db().execute('DELETE FROM card_legality WHERE format_id = ?', [format_id])
    sql = """INSERT INTO card_legality (format_id, card_id, legality)
        SELECT {format_id}, bq.id, 'Legal'
        FROM ({base_query}) AS bq
        WHERE name IN ({names})
    """.format(format_id=format_id, base_query=base_query(), names=', '.join(sqlescape(name) for name in new_list))
    db().execute(sql)
    # Check we got the right number of legal cards.
    n = db().value('SELECT COUNT(*) FROM card_legality WHERE format_id = ?', [format_id])
    if n != len(new_list):
        print("Found {n} pd legal cards in the database but the list was {len} long".format(n=n, len=len(new_list)))
        sql = 'SELECT bq.name FROM ({base_query}) AS bq WHERE bq.id IN (SELECT card_id FROM card_legality WHERE format_id = {format_id})'.format(base_query=base_query(), format_id=format_id)
        db_legal_list = [row['name'] for row in db().execute(sql)]
        print(set(new_list).symmetric_difference(set(db_legal_list)))
    return new_list

def update_cache():
    db().begin()
    db().execute('DROP TABLE IF EXISTS _cache_card')
    db().execute('CREATE TABLE _cache_card AS {base_query}'.format(base_query=base_query()))
    db().execute(db().create_index_query('idx_name_name', '_cache_card', 'name', prefix_width=142))
    db().commit()

def reindex():
    writer = WhooshWriter()
    writer.rewrite_index(get_all_cards())

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
        FORMAT_IDS[name] = db().last_insert_rowid()
    if name not in FORMAT_IDS.keys():
        return None
    return FORMAT_IDS[name]

def card_name(c):
    if c.get('layout') == 'meld':
        if c.get('name') == c.get('names')[2]:
            return c.get('names')[0]
        return c.get('name')
    return ' // '.join(c.get('names', [c.get('name')]))

def add_hardcoded_cards(cards):
    cards['Gleemox'] = {
        "text": "{T}: Add one mana of any color to your mana pool.\nThis card is banned.",
        "manaCost": "{0}",
        "type": "Artifact",
        "layout": "normal",
        "types": ["Artifact"],
        "cmc": 0,
        'imageName': 'gleemox',
        "legalities": [],
        "name": "Gleemox",
        "printings": ["PRM"],
        "rarity": "Rare"
    }
    fix_mtgjson_melded_cards_bug(cards)
    fix_double_faced_bug(cards)
    return cards

def get_all_cards():
    rs = db().execute(cached_base_query())
    return [card.Card(r) for r in rs]

def playable_layouts():
    return ['normal', 'token', 'double-faced', 'split', 'aftermath']

def try_find_card_id(c):
    card_id = None
    name = card_name(c)
    try:
        card_id = CARD_IDS[name]
        return (name, card_id)
    except KeyError:
        return (name, None)

def fix_mtgjson_melded_cards_bug(cards):
    for names in HARDCODED_MELD_NAMES:
        for name in names:
            if cards.get(name, None):
                cards[name]["names"] = names

def fix_mtgjson_melded_cards_array(cards):
    for c in cards:
        for group in HARDCODED_MELD_NAMES:
            if c.get('name') in group:
                c["names"] = group

def fix_double_faced_bug(cards):
    for c, names in HARDCODED_DFC_NAMES.items():
        cards[c]["names"] = names

def fix_double_faced_bug_array(cards):
    for c in cards:
        if c['name'] in HARDCODED_DFC_NAMES:
            c["names"] = HARDCODED_DFC_NAMES[c['name']]
