import datetime
from typing import Any, Dict, List, Optional, Set, Union

from magic import card, database, fetcher, mana, rotation
from magic.card import TableDescription
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
            try:
                update_database(last_updated)
                set_legal_cards()
            finally:
                # if the above fails for some reason, then things are probably bad
                # but we can't even start up a shell to fix unless the _cache_card table exists
                update_cache()
            reindex()
    except fetcher.FetchException:
        print('Unable to connect to Scryfall.')

def layouts() -> Dict[str, bool]:
    return {
        'adventure': True,
        'art_series': False,
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
        format_id=get_format_id('Penny Dreadful', True),
        card_props=', '.join('c.{name}'.format(name=name) for name in card.card_properties()),
        face_props=', '.join('f.{name}'.format(name=name) for name in card.face_properties() if name not in ['id', 'name']),
        where=where)

def base_query_lite() -> str:
    return """
        SELECT
            {base_query_props}
        FROM (
            SELECT {card_props}, {face_props}, f.name AS face_name
            FROM
                card AS c
            INNER JOIN
                face AS f ON c.id = f.card_id
            GROUP BY
                f.id
            ORDER BY
                f.card_id, f.position
        ) AS u
        GROUP BY u.id
    """.format(
        base_query_props=', '.join(prop['query'].format(table='u', column=name) for name, prop in card.base_query_lite_properties().items()),
        card_props=', '.join('c.{name}'.format(name=name) for name in card.card_properties()),
        face_props=', '.join('f.{name}'.format(name=name) for name in card.face_properties() if name not in ['id', 'name']),)


def update_database(new_date: datetime.datetime) -> None:
    db().begin('update_database')
    db().execute('DELETE FROM scryfall_version')
    db().execute('SET FOREIGN_KEY_CHECKS=0') # Avoid needing to drop _cache_card (which has an FK relationship with card) so that the database continues to function while we perform the update.
    db().execute("""
        DELETE FROM card_color;
        DELETE FROM card_color_identity;
        DELETE FROM card_legality;
        DELETE FROM card_bug;
        DELETE FROM face;
        DELETE FROM printing;
        DELETE FROM card;
        DELETE FROM `set`;
    """)
    for s in fetcher.all_sets():
        insert_set(s)
    every_card_printing = fetcher.all_cards()
    insert_cards(every_card_printing)
    update_pd_legality()
    db().execute('INSERT INTO scryfall_version (last_updated) VALUES (%s)', [dtutil.dt2ts(new_date)])
    db().execute('SET FOREIGN_KEY_CHECKS=1') # OK we are done monkeying with the db put the FK checks back in place and recreate _cache_card.
    update_cache()
    db().commit('update_database')

# Take Scryfall card descriptions and add them to the database. See also oracle.add_cards_and_update to also rebuild cache/reindex/etc.
# Iterate through all printings of each cards, building several sets of values to be provided to queries at the end.
# If we hit a new card, add it to the queries the several tables tracking cards: card, face, card_color, card_color_identity, printing
# If it's a printing of a card we already have, just add to the printing query.
# We need to wait until the end to add the meld results faces because they need to know the id of the card they are the reverse of before we can know their appropriate values.
def insert_cards(printings: List[CardDescription]) -> None:
    next_card_id = (db().value('SELECT MAX(id) FROM card') or 0) + 1
    values = determine_values(printings, next_card_id)
    insert_many('card', card.card_properties(), values['card'], ['id'])
    if values['card_color']: # We should not issue this query if we are only inserting colorless cards as they don't have an entry in this table.
        insert_many('card_color', card.card_color_properties(), values['card_color'])
        insert_many('card_color_identity', card.card_color_properties(), values['card_color_identity'])
    insert_many('printing', card.printing_properties(), values['printing'])
    insert_many('face', card.face_properties(), values['face'], ['position'])
    if values['card_legality']:
        insert_many('card_legality', card.card_legality_properties(), values['card_legality'], ['legality'])
    # Create the current Penny Dreadful format if necessary.
    get_format_id('Penny Dreadful', True)
    update_bugged_cards()

def determine_values(printings: List[CardDescription], next_card_id: int) -> Dict[str, List[Dict[str, Any]]]:
    # pylint: disable=too-many-locals
    cards: Dict[str, int] = {}
    card_values: List[Dict[str, Any]] = []
    face_values: List[Dict[str, Any]] = []
    meld_result_printings: List[CardDescription] = []
    card_color_values: List[Dict[str, Any]] = []
    card_color_identity_values: List[Dict[str, Any]] = []
    printing_values: List[Dict[str, Any]] = []
    card_legality_values: List[Dict[str, Any]] = []
    rarity_ids = {x['name']: x['id'] for x in db().select('SELECT id, name FROM rarity')}
    scryfall_to_internal_rarity = {
        'common': rarity_ids['Common'],
        'uncommon': rarity_ids['Uncommon'],
        'rare':  rarity_ids['Rare'],
        'mythic': rarity_ids['Mythic Rare']
    }
    sets = load_sets()
    colors = {c['symbol'].upper(): c['id'] for c in db().select('SELECT id, symbol FROM color ORDER BY id')}

    for p in printings:
        # Exclude art_series because they have the same name as real cards and that breaks things.
        # Exclude token because named tokens like "Ajani's Pridemate" and "Storm Crow" conflict with the cards with the same name. See #6156.
        if p['layout'] in ['art_series', 'token']:
            continue

        rarity_id = scryfall_to_internal_rarity[p['rarity'].strip()]

        try:
            set_id = sets[p['set']]
        except KeyError:
            print(f"We think we should have set {p['set']} but it's not in {sets} (from {p}) so updating sets")
            sets = update_sets()
            set_id = sets[p['set']]

        # If we already have the card, all we need is to record the next printing of it
        if p['name'] in cards:
            card_id = cards[p['name']]
            printing_values.append(printing_value(p, card_id, set_id, rarity_id))
            continue

        card_id = next_card_id
        next_card_id += 1
        cards[p['name']] = card_id
        card_values.append({'id': card_id, 'layout': p['layout']})

        if is_meld_result(p): # We don't make entries for a meld result until we know the card_ids of the front faces.
            meld_result_printings.append(p)
        elif p.get('card_faces') and p.get('layout') != 'meld':
            face_values += multiple_faces_values(p, card_id)
        else:
            face_values.append(single_face_value(p, card_id))
        for color in p.get('colors', []):
            color_id = colors[color]
            card_color_values.append({'card_id': card_id, 'color_id': color_id})
        for color in p.get('color_identity', []):
            color_id = colors[color]
            card_color_identity_values.append({'card_id': card_id, 'color_id': color_id})
        for format_, status in p.get('legalities', {}).items():
            if status == 'not_legal' or format_.capitalize() == 'Penny': # Skip 'Penny' from Scryfall as we'll create our own 'Penny Dreadful' format and set legality for it from legal_cards.txt.
                continue
            # Strictly speaking we could drop all this capitalizing and use what Scryfall sends us as the canonical name as it's just a holdover from mtgjson.
            format_id = get_format_id(format_.capitalize(), True)
            card_legality_values.append({'card_id': card_id, 'format_id': format_id, 'legality': status.capitalize()})

        cards[p['name']] = card_id
        printing_values.append(printing_value(p, card_id, set_id, rarity_id))

    for p in meld_result_printings:
        face_values += meld_face_values(p, cards)

    return {
        'card': card_values,
        'card_color': card_color_values,
        'card_color_identity': card_color_identity_values,
        'face': face_values,
        'printing': printing_values,
        'card_legality': card_legality_values
    }

def insert_many(table: str, properties: TableDescription, values: List[Dict[str, Any]], additional_columns: Optional[List[str]] = None) -> None:
    columns = additional_columns or []
    columns += [k for k, v in properties.items() if v.get('foreign_key')]
    columns += [name for name, prop in properties.items() if prop['scryfall']]
    query = f'INSERT INTO `{table}` ('
    query += ', '.join(columns)
    query += ') VALUES ('
    query += '), ('.join(', '.join(str(sqlescape(entry[column])) for column in columns) for entry in values)
    query += ')'
    db().execute(query)

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

def single_face_value(p: CardDescription, card_id: int, position: int = 1) -> Dict[str, Any]:
    if not card_id:
        raise InvalidDataException(f'Cannot insert a face without a card_id: {p}')
    result: Dict[str, Any] = {}
    result['card_id'] = card_id
    result['name'] = p['name'] # always present in scryfall
    result['mana_cost'] = p['mana_cost'] # always present in scryfall
    result['cmc'] = p['cmc'] # always present
    result['power'] = p.get('power')
    result['toughness'] = p.get('toughness')
    result['loyalty'] = p.get('loyalty')
    result['type_line'] = p.get('type_line', '')
    result['oracle_text'] = p.get('oracle_text', '')
    result['hand'] = p.get('hand_modifier')
    result['life'] = p.get('life_modifier')
    result['position'] = position
    return result

def multiple_faces_values(p: CardDescription, card_id: int) -> List[Dict[str, Any]]:
    card_faces = p.get('card_faces')
    if card_faces is None:
        raise InvalidArgumentException(f'Tried to insert_card_faces on a card without card_faces: {p} ({card_id})')
    first_face_cmc = mana.cmc(card_faces[0]['mana_cost'])
    position = 1
    face_values = []
    for face in card_faces:
        # Scryfall doesn't provide cmc on card_faces currently. See #5939.
        face['cmc'] = mana.cmc(face['mana_cost']) if face['mana_cost'] else first_face_cmc
        face_values.append(single_face_value(face, card_id, position))
        position += 1
    return face_values

def meld_face_values(p: CardDescription, cards: Dict[str, int]) -> List[Dict[str, Any]]:
    values = []
    all_parts = p.get('all_parts')
    if all_parts is None:
        raise InvalidArgumentException(f'Tried to insert_meld_result_faces on a card without all_parts: {p}')
    front_face_names = [part['name'] for part in all_parts if part['component'] == 'meld_part']
    card_ids = [cards[name] for name in front_face_names]
    for card_id in card_ids:
        values.append(single_face_value(p, card_id, 2))
    return values

def is_meld_result(p: CardDescription) -> bool:
    all_parts = p.get('all_parts')
    if all_parts is None or not p['layout'] == 'meld':
        return False
    meld_result_name = next(part['name'] for part in all_parts if part['component'] == 'meld_result')
    return p['name'] == meld_result_name

def load_sets() -> dict:
    return {s['code']: s['id'] for s in db().select('SELECT id, code FROM `set`')}

def insert_set(s: Any) -> int:
    sql = 'INSERT INTO `set` ('
    sql += ', '.join(name for name, prop in card.set_properties().items() if prop['scryfall'])
    sql += ') VALUES ('
    sql += ', '.join('%s' for name, prop in card.set_properties().items() if prop['scryfall'])
    sql += ')'
    values = [date2int(s.get(database2json(name)), name) for name, prop in card.set_properties().items() if prop['scryfall']]
    db().execute(sql, values)
    return db().last_insert_rowid()

def update_sets() -> dict:
    sets = load_sets()
    for s in fetcher.all_sets():
        if s['code'] not in sets.keys():
            insert_set(s)
    return load_sets()

def printing_value(p: CardDescription, card_id: int, set_id: int, rarity_id: int) -> Dict[str, Any]:
    # pylint: disable=too-many-locals
    if not card_id or not set_id:
        raise InvalidDataException(f'Cannot insert printing without card_id and set_id: {card_id}, {set_id}, {p}')
    result: Dict[str, Any] = {}
    result['card_id'] = card_id
    result['set_id'] = set_id
    result['rarity_id'] = rarity_id
    result['system_id'] = p.get('id')
    result['flavor'] = p.get('flavor_text')
    result['artist'] = p.get('artist')
    result['number'] = p.get('collector_number')
    result['watermark'] = p.get('watermark')
    result['reserved'] = 1 if p.get('reserved') else 0 # replace True and False with 1 and 0
    return result

def set_legal_cards(season: str = None) -> None:
    new_list: Set[str] = set()
    try:
        new_list = set(fetcher.legal_cards(force=True, season=season))
    except fetcher.FetchException:
        pass
    if season is None:
        format_id = get_format_id('Penny Dreadful')
    else:
        format_id = get_format_id('Penny Dreadful {season}'.format(season=season), True)

    if new_list == set() or new_list is None:
        return
    if season is not None:
        # Older formats don't change
        populated = db().select('SELECT id from card_legality WHERE format_id = %s LIMIT 1', [format_id])
        if populated:
            return

    # In case we get windows line endings.
    new_list = set(c.rstrip() for c in new_list)

    db().begin('set_legal_cards')
    db().execute('DELETE FROM card_legality WHERE format_id = %s', [format_id])
    db().execute('SET group_concat_max_len=100000')

    all_cards = db().select(base_query_lite())
    legal_cards = []
    for row in all_cards:
        if row['name'] in new_list:
            legal_cards.append("({format_id}, {card_id}, 'Legal')".format(format_id=format_id,
                                                                          card_id=row['id']))
    sql = """INSERT INTO card_legality (format_id, card_id, legality)
             VALUES {values}""".format(values=', '.join(legal_cards))

    db().execute(sql)
    db().commit('set_legal_cards')
    # Check we got the right number of legal cards.
    n = db().value('SELECT COUNT(*) FROM card_legality WHERE format_id = %s', [format_id])
    if n != len(new_list):
        print('Found {n} pd legal cards in the database but the list was {len} long'.format(n=n, len=len(new_list)))
        sql = 'SELECT bq.name FROM ({base_query}) AS bq WHERE bq.id IN (SELECT card_id FROM card_legality WHERE format_id = {format_id})'.format(base_query=base_query(), format_id=format_id)
        db_legal_list = [row['name'] for row in db().select(sql)]
        print(set(new_list).symmetric_difference(set(db_legal_list)))

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

# If you change this you probably need to change magic.card.name_query too.
def name_from_card_description(c: CardDescription) -> str:
    if c['layout'] in ['transform', 'flip', 'adventure']: # 'meld' has 'all_parts' not 'card_faces' so does not need to be included here despite having very similar behavior.
        return c['card_faces'][0]['name']
    if c.get('card_faces'):
        return ' // '.join([f['name'] for f in c.get('card_faces', [])])
    return c['name']
