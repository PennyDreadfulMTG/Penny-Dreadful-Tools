import datetime
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from magic import card, database, fetcher, rotation
from magic.card_description import CardDescription
from magic.database import create_table_def, db
from magic.models import Card
from magic.whoosh_write import WhooshWriter
from shared import dtutil
from shared.database import sqlescape
from shared.pd_exception import InvalidArgumentException, InvalidDataException

# Database setup for the magic package. Mostly internal. To interface with what the package knows about magic cards use the `oracle` module.

FORMAT_IDS: Dict[str, int] = {}
CARD_IDS: Dict[str, int] = {}

def init() -> None:
    try:
        last_updated = fetcher.scryfall_last_updated()
        if last_updated > database.last_updated():
            print('Database update required')
            update_database(last_updated)
            set_legal_cards()
            update_cache()
            reindex()
    except fetcher.FetchException:
        print('Unable to connect to Scryfall.')

def layouts() -> Dict[str, bool]:
    return {
        'augment': False,
        'double_faced_token': False,
        'emblem': False,
        'flip': True,
        'host': False,
        'leveler': True,
        'meld': True,
        'normal': True,
        'planar': False,
        'saga': True,
        'scheme': False,
        'split': True,
        'token': False,
        'transform': True,
        'vanguard': False
    }

def playable_layouts() -> List[str]:
    return [k for k, v in layouts().items() if v]

def cached_base_query(where: str = '(1 = 1)') -> str:
    return 'SELECT * FROM _cache_card AS c WHERE {where}'.format(where=where)

def base_query(where: str = '(1 = 1)') -> str:
    return """
        SELECT
            {base_query_props}
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
                    GROUP_CONCAT(CONCAT(fo.name, ':', cl.legality)) AS legalities
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
                GROUP_CONCAT(CONCAT(cb.description, '|', cb.classification, '|', cb.last_confirmed, '|', cb.url, '|', cb.from_bug_blog, '|', cb.bannable) SEPARATOR '_SEPARATOR_') AS bugs
            FROM
                card_bug AS cb
            GROUP BY
                cb.card_id
        ) AS bugs ON u.id = bugs.card_id
        WHERE u.id IN (SELECT c.id FROM card AS c INNER JOIN face AS f ON c.id = f.card_id WHERE {where})
        GROUP BY u.id
    """.format(
        base_query_props=', '.join(prop['query'].format(table='u', column=name) for name, prop in card.base_query_properties().items()),
        format_id=get_format_id('Penny Dreadful'),
        card_props=', '.join('c.{name}'.format(name=name) for name in card.card_properties()),
        face_props=', '.join('f.{name}'.format(name=name) for name in card.face_properties() if name not in ['id', 'name']),
        where=where)

def update_database(new_date: datetime.datetime) -> None:
    db().begin('update_database')
    db().execute('DELETE FROM scryfall_version')
    db().execute('DROP TABLE IF EXISTS _cache_card') # We can't delete our data if we have FKs referencing it.
    db().execute("""
        DELETE FROM card_alias;
        DELETE FROM card_color;
        DELETE FROM card_color_identity;
        DELETE FROM card_legality;
        DELETE FROM card_subtype;
        DELETE FROM card_supertype;
        DELETE FROM card_bug;
        DELETE FROM face;
        DELETE FROM printing;
        DELETE FROM card;
        DELETE FROM `set`;
    """)
    every_card_printing = fetcher.all_cards()
    cards = []
    melded_faces, cards = [], {}
    for p in every_card_printing:
        pos = 1
        faces = p.get('card_faces') or [p]
        for f in faces:
            f['position'] = pos
            pos += 1
            f['names'] = names(p)
            c = cards.get(f['name'], {})
            c.update(p)
            c.update(f)
            c['printings'] = c.get('printings', []) + [p]
            cards[f['name']] = c
    for c in cards.values():
        # c['position'] = c['names'].index(c['name']) # BAKERT this wont' work til names is ordered correctly OR will it not even work then as own name comes first???
        if c['position'] is None:
            raise Exception('no position') # BAKERT
        c['type_line'] = c.get('type_line', '').replace('—', '-')
        if is_meld_result(c):
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
    for s in sets:
        insert_set(s)
    check_layouts() # Check that the hardcoded list of layouts we're about to use is still valid.
    rs = db().select('SELECT id, name FROM rarity')
    for row in rs:
        db().execute('UPDATE printing SET rarity_id = %s WHERE rarity = %s', [row['id'], row['name']])
    # Create the current Penny Dreadful format.
    get_format_id('Penny Dreadful', True)
    update_bugged_cards()
    update_pd_legality()
    db().execute('INSERT INTO scryfall_version (last_updated) VALUES (%s)', [dtutil.dt2ts(new_date)])
    db().commit('update_database')

def is_meld_result(c) -> bool:
    return c.get('layout') == 'meld' and len([p for p in c.get('all_parts', []) if p['name'] == c['name'] and p['component'] == 'meld_result']) > 0

def check_layouts() -> None:
    rs = db().select('SELECT DISTINCT layout FROM card')
    if sorted([row['layout'] for row in rs]) != sorted(layouts().keys()):
        print('WARNING. There has been a change in layouts. The update to 0 CMC may no longer be valid. You may also want to add it to the layouts function. Comparing {old} with {new}.'.format(old=sorted(layouts().keys()), new=sorted([row['layout'] for row in rs])))

def update_bugged_cards() -> None:
    bugs = fetcher.bugged_cards()
    if bugs is None:
        return
    db().begin('update_bugged_cards')
    db().execute('DELETE FROM card_bug')
    for bug in bugs:
        last_confirmed_ts = dtutil.parse_to_ts(bug['last_updated'], '%Y-%m-%d %H:%M:%S', dtutil.UTC_TZ)
        name = bug['card'].split(' // ')[0] # We need a face name from split cards - we don't have combined card names yet.
        card_id = db().value('SELECT card_id FROM face WHERE name = %s', [name])
        if card_id is None:
            print('UNKNOWN BUGGED CARD: {card}'.format(card=bug['card']))
            continue
        db().execute('INSERT INTO card_bug (card_id, description, classification, last_confirmed, url, from_bug_blog, bannable) VALUES (%s, %s, %s, %s, %s, %s, %s)', [card_id, bug['description'], bug['category'], last_confirmed_ts, bug['url'], bug['bug_blog'], bug['bannable']])
    db().commit('update_bugged_cards')

def update_pd_legality() -> None:
    for s in rotation.SEASONS:
        if s == rotation.current_season_code():
            break
        set_legal_cards(season=s)

def insert_card(c: Any, update_index: bool = True) -> None:
    name, card_id = try_find_card_id(c)
    if card_id is None:
        sql = 'INSERT INTO card ('
        sql += ', '.join(name for name, prop in card.card_properties().items() if prop['scryfall'])
        sql += ') VALUES ('
        sql += ', '.join('%s' for name, prop in card.card_properties().items() if prop['scryfall'])
        sql += ')'
        values = [c.get(database2json(name)) for name, prop in card.card_properties().items() if prop['scryfall']]
        db().execute(sql, values)
        card_id = db().last_insert_rowid()
        CARD_IDS[name] = card_id
    c['oracle_text'] = c.get('oracle_text', '')
    # BAKERT c['name_ascii'] = card.unaccent(c.get('name'))
    # BAKERT c['search_text'] = re.sub(r'\([^\)]+\)', '', c['oracle_text'])
    c['card_id'] = card_id
    # c['position'] = 1 if not c.get('names') else c.get('names', [c.get('name')]).index(c.get('name')) + 1
    sql = 'INSERT INTO face ('
    sql += ', '.join(name for name, prop in card.face_properties().items() if not prop['primary_key'])
    sql += ') VALUES ('
    sql += ', '.join('%s' for name, prop in card.face_properties().items() if not prop['primary_key'])
    sql += ')'
    values = [c.get(database2json(name)) for name, prop in card.face_properties().items() if not prop['primary_key']]
    try:
        db().execute(sql, values)
    except database.DatabaseException:
        print(c)
        raise
    for color in c.get('colors', []):
        color_id = db().value('SELECT id FROM color WHERE symbol = %s', [color.capitalize()])
        # INSERT IGNORE INTO because some cards have multiple faces with the same color. See DFCs and What // When // Where // Who // Why.
        db().execute('INSERT IGNORE INTO card_color (card_id, color_id) VALUES (%s, %s)', [card_id, color_id])
    for symbol in c.get('color_identity', []):
        color_id = db().value('SELECT id FROM color WHERE symbol = %s', [symbol])
        # INSERT IGNORE INTO because some cards have multiple faces with the same color identity. See DFCs and What // When // Where // Who // Why.
        db().execute('INSERT IGNORE INTO card_color_identity (card_id, color_id) VALUES (%s, %s)', [card_id, color_id])
    for supertype in supertypes(c.get('type', '')):
        # INSERT IGNORE INTO because some cards have multiple faces with the same supertype. See DFCs and What // When // Where // Who // Why.
        db().execute('INSERT  IGNORE INTO card_supertype (card_id, supertype) VALUES (%s, %s)', [card_id, supertype])
    for subtype in subtypes(c.get('type_line', '')):
        # INSERT IGNORE INTO because some cards have multiple faces with the same subtype. See DFCs and What // When // Where // Who // Why.
        db().execute('INSERT IGNORE INTO card_subtype (card_id, subtype) VALUES (%s, %s)', [card_id, subtype])
    for f, status in c.get('legalities', []).items():
        if status == 'not_legal':
            continue
        # BAKERT strictly speaking we could drop all this capitalizing as it's just a holdover from mtgjson.
        name = f.capitalize()
        format_id = get_format_id(name, True)
        # INSERT IGNORE INTO because some cards have multiple faces with the same legality. See DFCs and What // When // Where // Who // Why.
        db().execute('INSERT IGNORE INTO card_legality (card_id, format_id, legality) VALUES (%s, %s, %s)', [card_id, format_id, status.capitalize()])
    if update_index:
        writer = WhooshWriter()
        c['id'] = c['cardId'] # BAKERT cardId? I don't think that exists any more.
        writer.update_card(c)

def insert_set(s: Any) -> None:
    sql = 'INSERT INTO `set` ('
    sql += ', '.join(name for name, prop in card.set_properties().items() if prop['scryfall'])
    sql += ') VALUES ('
    sql += ', '.join('%s' for name, prop in card.set_properties().items() if prop['scryfall'])
    sql += ')'
    values = [date2int(s.get(database2json(name)), name) for name, prop in card.set_properties().items() if prop['scryfall']]
    db().execute(sql, values)
    set_id = db().last_insert_rowid()
    set_cards = s.get('cards', [])
    for c in set_cards:
        _, card_id = try_find_card_id(c)
        if card_id is None:
            raise InvalidDataException("Can't find id for: '{n}': {ns}".format(n=c['name'], ns='; '.join(c.get('names', []))))
        sql = 'INSERT INTO printing (card_id, set_id, '
        sql += ', '.join(name for name, prop in card.printing_properties().items() if prop['scryfall'])
        sql += ') VALUES (%s, %s, '
        sql += ', '.join('%s' for name, prop in card.printing_properties().items() if prop['scryfall'])
        sql += ')'
        cards_values = [card_id, set_id] + [c.get(database2json(name)) for name, prop in card.printing_properties().items() if prop['scryfall']]
        db().execute(sql, cards_values)

def set_legal_cards(season: str = None) -> List[str]:
    new_list = ['']
    try:
        new_list = fetcher.legal_cards(force=True, season=season)
    except fetcher.FetchException:
        pass
    if season is None:
        format_id = get_format_id('Penny Dreadful')
    else:
        format_id = get_format_id('Penny Dreadful {season}'.format(season=season), True)

    if new_list == [''] or new_list is None:
        return []
    db().begin('set_legal_cards')
    db().execute('DELETE FROM card_legality WHERE format_id = %s', [format_id])
    db().execute('SET group_concat_max_len=100000')
    sql = """INSERT INTO card_legality (format_id, card_id, legality)
        SELECT {format_id}, bq.id, 'Legal'
        FROM ({base_query}) AS bq
        WHERE name IN ({names})
    """.format(format_id=format_id, base_query=base_query(), names=', '.join(sqlescape(name) for name in new_list))
    db().execute(sql)
    db().commit('set_legal_cards')
    # Check we got the right number of legal cards.
    n = db().value('SELECT COUNT(*) FROM card_legality WHERE format_id = %s', [format_id])
    if n != len(new_list):
        print('Found {n} pd legal cards in the database but the list was {len} long'.format(n=n, len=len(new_list)))
        sql = 'SELECT bq.name FROM ({base_query}) AS bq WHERE bq.id IN (SELECT card_id FROM card_legality WHERE format_id = {format_id})'.format(base_query=base_query(), format_id=format_id)
        db_legal_list = [row['name'] for row in db().select(sql)]
        print(set(new_list).symmetric_difference(set(db_legal_list)))
    return new_list

def update_cache() -> None:
    db().execute('DROP TABLE IF EXISTS _new_cache_card')
    db().execute('SET group_concat_max_len=100000')
    db().execute(create_table_def('_new_cache_card', card.base_query_properties(), base_query()))
    db().execute('CREATE UNIQUE INDEX idx_u_card_id ON _new_cache_card (card_id)')
    db().execute('CREATE UNIQUE INDEX idx_u_name ON _new_cache_card (name(142))')
    db().execute('CREATE UNIQUE INDEX idx_u_names ON _new_cache_card (names(142))')
    db().execute('DROP TABLE IF EXISTS _old_cache_card')
    db().execute('CREATE TABLE IF NOT EXISTS _cache_card (_ INT)') # Prevent error in RENAME TABLE below if bootstrapping.
    db().execute('RENAME TABLE _cache_card TO _old_cache_card, _new_cache_card TO _cache_card')
    db().execute('DROP TABLE IF EXISTS _old_cache_card')

def reindex() -> None:
    writer = WhooshWriter()
    cs = get_all_cards()
    for alias, name in fetcher.card_aliases():
        for c in cs:
            if c.name == name:
                c.names.append(alias)
    writer.rewrite_index(cs)

# BAKERT is this necessary? do we still have a system_id?
def database2json(propname: str) -> str:
    if propname == 'system_id':
        propname = 'id'
    return propname

def date2int(s: str, name: str) -> Union[str, float]:
    if name == 'released_at':
        return dtutil.parse_to_ts(s, '%Y-%m-%d', dtutil.WOTC_TZ)
    return s

# I'm not sure this belong here, but it's here for now.
def get_format_id(name: str, allow_create: bool = False) -> int:
    if len(FORMAT_IDS) == 0:
        rs = db().select('SELECT id, name FROM format')
        for row in rs:
            FORMAT_IDS[row['name']] = row['id']
    if name not in FORMAT_IDS.keys() and allow_create:
        db().execute('INSERT INTO format (name) VALUES (%s)', [name])
        FORMAT_IDS[name] = db().last_insert_rowid()
    if name not in FORMAT_IDS.keys():
        raise InvalidArgumentException('Unknown format: {name}'.format(name=name))
    return FORMAT_IDS[name]

def get_format_id_from_season_id(season_id: int) -> int:
    season_code = rotation.SEASONS[int(season_id) - 1]
    if season_code == rotation.current_season_code():
        format_name = 'Penny Dreadful'
    else:
        format_name = 'Penny Dreadful {f}'.format(f=season_code)
    return get_format_id(format_name)

def card_name(c: CardDescription) -> str:
    if c.get('layout') == 'meld':
        if c.get('name', '') == c.get('names', [])[2]:
            return c.get('names', [])[0]
        return c.get('name', '')
    return ' // '.join(c.get('names', [c.get('name', '')]))

def get_all_cards() -> List[Card]:
    rs = db().select(cached_base_query())
    return [Card(r) for r in rs]

def try_find_card_id(c: CardDescription) -> Tuple[str, Optional[int]]:
    card_id = None
    name = card_name(c)
    try:
        card_id = CARD_IDS[name]
        return (name, card_id)
    except KeyError:
        return (name, None)

def names(c: CardDescription): # BAKERT needs a type
    if not c.get('all_parts') or c.get('layout') == 'token':
        return [c['name']]
    known_components = ['combo_piece', 'token', 'meld_part', 'meld_result']
    if [part for part in c['all_parts'] if part.get('component') not in known_components]:
        raise Exception(f'Found an unexpected component type in {c}') # BAKERT exception type
    # Do this in two steps to get meld cards in the right order (meld result last).
    card_names = [part['name'] for part in c['all_parts'] if part.get('component') not in ['meld_result', 'token', 'combo_piece']]
    card_names = card_names + [part['name'] for part in c['all_parts'] if part.get('component') == 'meld_result']
    if not card_names:
        return [c['name']]
    # For some reason some Schemes and Planes refer to their tokens but not themselves in Scryfall data.
    if c['name'] not in card_names and re.match('^(Plane)|((Ongoing )?Scheme)', c['type_line']):
        return [c['name']]
    if c['name'] not in card_names:
        raise InvalidDataException(f'A non-Scheme card does not have its name but does have an all_parts - this is unexpected {names}: {c}')
    return card_names

def supertypes(type_line: str) -> List[str]:
    types = type_line.split('-')[0]
    possible_supertypes = ['Legendary', 'Snow', 'Basic', 'Ongoing', 'World', 'Token', 'Host', 'Elite']
    stypes = []
    for possible in possible_supertypes:
        if possible in types:
            stypes.append(possible)
    return stypes

def subtypes(type_line: str) -> List[str]:
    if '-' not in type_line:
        return []
    return type_line.split(' - ')[1].split(' ')
