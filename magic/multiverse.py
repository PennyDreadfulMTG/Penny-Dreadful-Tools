import datetime
from typing import Any, Dict, List, Optional, Union

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
    raw_sets = fetcher.all_sets()
    sets = {}
    for s in raw_sets:
        sets[s['code']] = insert_set(s)
    every_card_printing = fetcher.all_cards()
    cards: Dict[str, int] = {}
    meld_results = []
    card_id: Optional[int]
    for p in [p for p in every_card_printing if p['name'] != 'Little Girl']: # Exclude little girl because hw mana is a problem rn.
        if p['name'] in cards:
            card_id = cards[p['name']]
        else:
            if not is_meld_result(p):
                card_id = insert_card(p, update_index=False)
                if card_id:
                    cards[p['name']] = card_id
            else:
                meld_results.append(p)
        try:
            set_id = sets[p['set']]
        except KeyError:
            raise InvalidDataException(f"We think we should have set {p['set']} but it's not in {sets} (from {p})")
        if card_id:
            insert_printing(p, card_id, set_id)
    for p in meld_results:
        insert_meld_result_faces(p, cards)
    rs = db().select('SELECT id, name FROM rarity')
    for row in rs:
        db().execute('UPDATE printing SET rarity_id = %s WHERE rarity = %s', [row['id'], row['name']])
    # Create the current Penny Dreadful format.
    get_format_id('Penny Dreadful', True)
    update_bugged_cards()
    update_pd_legality()
    db().execute('INSERT INTO scryfall_version (last_updated) VALUES (%s)', [dtutil.dt2ts(new_date)])
    db().commit('update_database')

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

def insert_card(p: Any, update_index: bool = True) -> Optional[int]:
    if p['layout'] in ['augment', 'emblem', 'host', 'planar', 'scheme', 'vanguard']:
        return None # See #5927
    # Preprocess card partly for sanity but partly just to match what we used to get from mtgjson to make migration easier.
    sql = 'INSERT INTO card ('
    sql += ', '.join(name for name, prop in card.card_properties().items() if prop['scryfall'])
    sql += ') VALUES ('
    sql += ', '.join('%s' for name, prop in card.card_properties().items() if prop['scryfall'])
    sql += ')'
    values = [p.get(database2json(name)) for name, prop in card.card_properties().items() if prop['scryfall']]
    db().execute(sql, values)
    card_id = db().last_insert_rowid()
    # 'meld' is in the list of normal cards here but is handled differently at a higher level. See above.
    if p['layout'] in ['leveler', 'meld', 'normal', 'saga', 'token']:
        insert_face(p, card_id)
    elif p['layout'] in ['double_faced_token', 'flip', 'split', 'transform']:
        insert_card_faces(p, card_id)
    else:
        raise InvalidDataException(f"Unknown layout {p['layout']}")
    for color in p.get('colors', []):
        color_id = db().value('SELECT id FROM color WHERE symbol = %s', [color.capitalize()])
        # INSERT IGNORE INTO because some cards have multiple faces with the same color. See DFCs and What // When // Where // Who // Why.
        db().execute('INSERT IGNORE INTO card_color (card_id, color_id) VALUES (%s, %s)', [card_id, color_id])
    for symbol in p.get('color_identity', []):
        color_id = db().value('SELECT id FROM color WHERE symbol = %s', [symbol])
        # INSERT IGNORE INTO because some cards have multiple faces with the same color identity. See DFCs and What // When // Where // Who // Why.
        db().execute('INSERT IGNORE INTO card_color_identity (card_id, color_id) VALUES (%s, %s)', [card_id, color_id])
    for supertype in supertypes(p.get('type', '')):
        # INSERT IGNORE INTO because some cards have multiple faces with the same supertype. See DFCs and What // When // Where // Who // Why.
        db().execute('INSERT  IGNORE INTO card_supertype (card_id, supertype) VALUES (%s, %s)', [card_id, supertype])
    for subtype in subtypes(p.get('type_line', '')):
        # INSERT IGNORE INTO because some cards have multiple faces with the same subtype. See DFCs and What // When // Where // Who // Why.
        db().execute('INSERT IGNORE INTO card_subtype (card_id, subtype) VALUES (%s, %s)', [card_id, subtype])
    for f, status in p.get('legalities', []).items():
        if status == 'not_legal':
            continue
        # Strictly speaking we could drop all this capitalizing and use what Scryfall sends us as the canonical name as it's just a holdover from mtgjson.
        name = f.capitalize()
        format_id = get_format_id(name, True)
        # INSERT IGNORE INTO because some cards have multiple faces with the same legality. See DFCs and What // When // Where // Who // Why.
        db().execute('INSERT IGNORE INTO card_legality (card_id, format_id, legality) VALUES (%s, %s, %s)', [card_id, format_id, status.capitalize()])
    if update_index:
        writer = WhooshWriter()
        writer.update_card(p)
    return card_id

def insert_face(p: CardDescription, card_id: int, position: int = 1) -> None:
    if not card_id:
        raise InvalidDataException(f'Cannot insert a face without a card_id: {p}')
    p['oracle_text'] = p.get('oracle_text', '')
    sql = 'INSERT INTO face (card_id, position, '
    sql += ', '.join(name for name, prop in card.face_properties().items() if prop['scryfall'])
    sql += ') VALUES (%s, %s, '
    sql += ', '.join('%s' for name, prop in card.face_properties().items() if prop['scryfall'])
    sql += ')'
    values = [card_id, position] + [p.get(database2json(name)) for name, prop in card.face_properties().items() if prop['scryfall']] # type: ignore
    db().execute(sql, values)

def insert_card_faces(p: CardDescription, card_id: int) -> None:
    position = 1
    for face in p['card_faces']: # type: ignore
        insert_face(face, card_id, position)
        position += 1

def insert_meld_result_faces(p: CardDescription, cards: Dict[str, int]) -> None:
    front_face_names = [part['name'] for part in p['all_parts'] if part['component'] == 'meld_part'] # type: ignore
    card_ids = [cards[name] for name in front_face_names]
    for card_id in card_ids: # type: ignore
        insert_face(p, card_id, 2)

def is_meld_result(p: CardDescription) -> bool:
    if not p['layout'] == 'meld' or not p.get('all_parts'):
        return False
    meld_result_name = next(part['name'] for part in p['all_parts'] if part['component'] == 'meld_result') # type: ignore
    return p['name'] == meld_result_name

def insert_set(s: Any) -> int:
    sql = 'INSERT INTO `set` ('
    sql += ', '.join(name for name, prop in card.set_properties().items() if prop['scryfall'])
    sql += ') VALUES ('
    sql += ', '.join('%s' for name, prop in card.set_properties().items() if prop['scryfall'])
    sql += ')'
    values = [date2int(s.get(database2json(name)), name) for name, prop in card.set_properties().items() if prop['scryfall']]
    db().execute(sql, values)
    return db().last_insert_rowid()

def insert_printing(p: CardDescription, card_id: int, set_id: int) -> None:
    if not card_id or not set_id:
        raise InvalidDataException(f'Cannot insert printing without card_id and set_id: {card_id}, {set_id}, {p}')
    sql = 'INSERT INTO printing (card_id, set_id, '
    sql += ', '.join(name for name, prop in card.printing_properties().items() if prop['scryfall'])
    sql += ') VALUES (%s, %s, '
    sql += ', '.join('%s' for name, prop in card.printing_properties().items() if prop['scryfall'])
    sql += ')'
    cards_values = [card_id, set_id] + [p.get(database2json(name)) for name, prop in card.printing_properties().items() if prop['scryfall']] # type: ignore
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

def supertypes(type_line: str) -> List[str]:
    types = type_line.split('-')[0]
    possible_supertypes = ['Basic', 'Legendary', 'Ongoing', 'Snow', 'World']
    sts = []
    for possible in possible_supertypes:
        if possible in types:
            sts.append(possible)
    return sts

def subtypes(type_line: str) -> List[str]:
    if ' - ' not in type_line:
        return []
    return type_line.split(' - ')[1].split(' ')
