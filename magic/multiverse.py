import asyncio
import datetime
import json
import os
import re
from typing import Any

from magic import card, database, fetcher, layout, mana, seasons
from magic.abc import CardDescription
from magic.card import TableDescription
from magic.database import create_table_def, db
from magic.models import Card
from shared import configuration, dtutil
from shared.database import sqlescape
from shared.pd_exception import InvalidArgumentException, InvalidDataException

# Database setup for the magic package. Mostly internal. To interface with what the package knows about magic cards use the `oracle` module.

FORMAT_IDS: dict[str, int] = {}

# This is only a fallback
KNOWN_MELDS = ['Brisela, Voice of Nightmares', 'Chittering Host', 'Hanweir, the Writhing Township',
               'Urza, Planeswalker', 'Mishra, Lost to Phyrexia', 'Ragnarok, Divine Deliverance']

def init(force: bool = False) -> bool:
    return asyncio.run(init_async(force))

async def init_async(force: bool = False) -> bool:
    try:
        last_updated = await fetcher.scryfall_last_updated_async()
        if last_updated > database.last_updated() or force:
            if configuration.prevent_cards_db_updates.get():
                print('Not updating cards db because prevent_cards_db_updates is True')
                return False
            print('Database update required')
            try:
                success = await update_database_async(last_updated)
                if success:
                    await set_legal_cards_async()
            finally:
                # if the above fails for some reason, then things are probably bad
                # but we can't even start up a shell to fix unless the _cache_card table exists
                rebuild_cache()
            return success
    except fetcher.FetchException:
        print('Unable to connect to Scryfall.')
    return False

def cached_base_query(where: str = 'TRUE') -> str:
    return f'SELECT * FROM _cache_card AS c WHERE {where}'

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
        LEFT JOIN (
            SELECT
                fn.card_id,
                GROUP_CONCAT(fn.flavor_name SEPARATOR '|') AS flavor_names
            FROM
                card_flavor_name AS fn
            GROUP BY
                fn.card_id
        ) AS fn ON fn.card_id = u.id
        WHERE u.id IN (SELECT c.id FROM card AS c INNER JOIN face AS f ON c.id = f.card_id WHERE {where})
        GROUP BY u.id
    """.format(
        base_query_props=', '.join(prop['query'].format(table='u', column=name) for name, prop in card.base_query_properties().items()),
        format_id=get_format_id(f'Penny Dreadful {seasons.current_season_code()}', True),
        card_props=', '.join(f'c.{name}' for name in card.card_properties()),
        face_props=', '.join(f'f.{name}' for name in card.face_properties() if name not in ['id', 'name']),
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
        LEFT JOIN (
            SELECT
                fn.card_id,
                GROUP_CONCAT(fn.flavor_name SEPARATOR '|') AS flavor_names
            FROM
                card_flavor_name AS fn
            GROUP BY
                fn.card_id
        ) AS fn ON fn.card_id = u.id
        GROUP BY u.id
    """.format(
        base_query_props=', '.join(prop['query'].format(table='u', column=name) for name, prop in card.base_query_lite_properties().items()),
        card_props=', '.join(f'c.{name}' for name in card.card_properties()),
        face_props=', '.join(f'f.{name}' for name in card.face_properties() if name not in ['id', 'name']))


async def update_database_async(new_date: datetime.datetime) -> bool:
    try:
        sets = await fetcher.all_sets_async()
        if os.path.exists('scryfall-default-cards.json'):
            with open('scryfall-default-cards.json', encoding='utf-8') as f:
                all_cards = json.load(f)
                download_uri = None
        else:
            all_cards, download_uri = await fetcher.all_cards_async()
    except Exception as e:
        print(f'Aborting database update because fetching from Scryfall failed: {e}')
        return False
    try:
        await insert_cards(new_date, sets, all_cards)
        if download_uri:
            configuration.last_good_bulk_data.value = download_uri
    except Exception as e:
        print(f'Failed to load current bulk data, using fallback: {e}')
        all_cards, download_uri = await fetcher.all_cards_async(force_last_good=True)
        await insert_cards(new_date, sets, all_cards)
    return True

async def insert_cards(new_date: datetime.datetime, sets: list[dict[str, Any]], all_cards: list[CardDescription]) -> None:
    db().begin('update_database')
    db().execute('DELETE FROM scryfall_version')
    db().execute('SET FOREIGN_KEY_CHECKS=0')  # Avoid needing to drop _cache_card (which has an FK relationship with card) so that the database continues to function while we perform the update.
    db().execute('DELETE FROM card_color')
    db().execute('DELETE FROM card_color_identity')
    db().execute('DELETE FROM card_produced_mana')
    db().execute('DELETE FROM card_legality')
    db().execute('DELETE FROM card_bug')
    db().execute('DELETE FROM face')
    db().execute('DELETE FROM printing')
    db().execute('DELETE FROM card_flavor_name')
    db().execute('DELETE FROM card')
    db().execute('DELETE FROM `set`')
    for s in sets:
        insert_set(s)
    every_card_printing = all_cards
    await insert_cards_async(every_card_printing)
    await update_pd_legality_async()
    db().execute('INSERT INTO scryfall_version (last_updated) VALUES (%s)', [dtutil.dt2ts(new_date)])
    db().execute('SET FOREIGN_KEY_CHECKS=1')  # OK we are done monkeying with the db put the FK checks back in place and recreate _cache_card.
    rebuild_cache()
    db().commit('update_database')

# Take Scryfall card descriptions and add them to the database. See also oracle.add_cards_and_update_async to also rebuild cache/reindex/etc.
async def insert_cards_async(printings: list[CardDescription]) -> list[int]:
    next_card_id = (db().value('SELECT MAX(id) FROM card') or 0) + 1
    values = await determine_values_async(printings, next_card_id)
    insert_many('card', card.card_properties(), values['card'], ['id'])
    if values['card_color']:  # We should not issue this query if we are only inserting colorless cards as they don't have an entry in this table.
        insert_many('card_color', card.card_color_properties(), values['card_color'])
        insert_many('card_color_identity', card.card_color_properties(), values['card_color_identity'])
        insert_many('card_produced_mana', card.card_color_properties(), values['card_produced_mana'])
    insert_many('printing', card.printing_properties(), values['printing'])
    insert_many('card_flavor_name', card.card_flavor_name_properties(), values['flavor_name'])
    insert_many('face', card.face_properties(), values['face'], ['position'])
    if values['card_legality']:
        insert_many('card_legality', card.card_legality_properties(), values['card_legality'], ['legality'])
    # Create the current Penny Dreadful format if necessary.
    get_format_id(f'Penny Dreadful {seasons.current_season_code()}', True)
    await update_bugged_cards_async()
    return [c['id'] for c in values['card']]

async def determine_values_async(printings: list[CardDescription], next_card_id: int) -> dict[str, list[dict[str, Any]]]:
    cards: dict[str, int] = {}
    flavor_names: dict[str, int] = {}
    card_values: list[dict[str, Any]] = []
    face_values: list[dict[str, Any]] = []
    meld_result_printings: list[CardDescription] = []
    card_color_values: list[dict[str, Any]] = []
    card_color_identity_values: list[dict[str, Any]] = []
    card_produced_mana_values: list[dict[str, Any]] = []
    printing_values: list[dict[str, Any]] = []
    card_legality_values: list[dict[str, Any]] = []
    rarity_ids = {x['name']: x['id'] for x in db().select('SELECT id, name FROM rarity')}
    scryfall_to_internal_rarity = {
        'common': rarity_ids['Common'],
        'uncommon': rarity_ids['Uncommon'],
        'rare': rarity_ids['Rare'],
        'mythic': rarity_ids['Mythic Rare'],
        'special': rarity_ids['Rare'],
        'bonus': rarity_ids['Mythic Rare'],

    }
    sets = load_sets()
    colors = {c['symbol'].upper(): c['id'] for c in db().select('SELECT id, symbol FROM color ORDER BY id')}

    BAD_DRAGONS = ['Bloomvine Regent', 'Marang River Regent']

    for p in printings:
        try:
            if p.get('name') in BAD_DRAGONS:
                p['layout'] = 'adventure'

            if p.get('layout') not in layout.all_layouts():
                layout.report_missing_layout(p.get('layout'))
                continue

            if p.get('layout') == 'reversible_card':
                continue  # More trouble than it's worth for now.

            if p.get('layout') not in layout.uses_canonical_namespace():
                continue

            if 'playtest' in p.get('promo_types', []):
                continue

            # Exclude "Card"s which is a whole group of weird things, and also any tokens that have a playable layout.
            if re.search(r'\b(token|card)\b', p.get('type_line', ''), re.IGNORECASE):
                continue

            rarity_id = scryfall_to_internal_rarity[p['rarity'].strip()]

            try:
                set_id = sets[p['set']]
            except KeyError:
                print(f"We think we should have set {p['set']} but it's not in {sets} (from {p}) so updating sets")
                sets = await update_sets_async()
                try:
                    set_id = sets[p['set']]
                except KeyError:
                    print(f'We still don\'t have {p["set"]}, skipping {p["name"]}')
                    continue

            # If we already have the card, all we need is to record the next printing of it
            if p['name'] in cards:
                card_id = cards[p['name']]
                printing_values.append(printing_value(p, card_id, set_id, rarity_id))
                if p.get('flavor_name'):
                    flavor_names[p['flavor_name']] = card_id
                continue

            card_id = next_card_id
            next_card_id += 1
            cards[p['name']] = card_id
            card_values.append({'id': card_id, 'oracle_id': p['oracle_id'], 'layout': p['layout']})

            if is_meld_result(p):  # We don't make entries for a meld result until we know the card_ids of the front faces.
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
            for color in [c for c in p.get('produced_mana', []) if c not in ['T']]:  # Ignore Sole Performer and its production of "T". Scryfall itself doesn't allow searching for that.
                color_id = colors[color]
                card_produced_mana_values.append({'card_id': card_id, 'color_id': color_id})
            # DFCs store their colors in their faces, not at the top level. See #9022.
            for color in face_colors(p):
                color_id = colors[color]
                card_color_values.append({'card_id': card_id, 'color_id': color_id})
            for format_, status in p.get('legalities', {}).items():
                if status == 'not_legal' or format_.capitalize() == 'Penny':  # Skip 'Penny' from Scryfall as we'll create our own 'Penny Dreadful' format and set legality for it from legal_cards.txt.
                    continue
                # Strictly speaking we could drop all this capitalizing and use what Scryfall sends us as the canonical name as it's just a holdover from mtgjson.
                format_id = get_format_id(format_.capitalize(), True)
                card_legality_values.append({'card_id': card_id, 'format_id': format_id, 'legality': status.capitalize()})

            cards[p['name']] = card_id
            printing_values.append(printing_value(p, card_id, set_id, rarity_id))
            if p.get('flavor_name'):
                flavor_names[p['flavor_name']] = card_id
            if p.get('printed_name') and p.get('lang') == 'en' and p['printed_name'] != p['name']:
                flavor_names[p['printed_name']] = card_id
        except Exception as e:
            print(f'Exception `{e} ({type(e)})` while importing card: {repr(p)}')
            raise InvalidDataException() from e

    for p in meld_result_printings:
        face_values += meld_face_values(p, cards)

    flavor_name_values = [{'card_id': card_id, 'flavor_name': flavor_name} for flavor_name, card_id in flavor_names.items()]

    return {
        'card': card_values,
        'card_color': card_color_values,
        'card_color_identity': card_color_identity_values,
        'card_produced_mana': card_produced_mana_values,
        'face': face_values,
        'printing': printing_values,
        'card_legality': card_legality_values,
        'flavor_name': flavor_name_values,
    }

def face_colors(p: CardDescription) -> set[str]:
    colors = set()
    for f in p.get('card_faces', []):
        for color in f.get('colors', []):
            colors.add(color)
    return colors

def insert_many(table: str, properties: TableDescription, values: list[dict[str, Any]], additional_columns: list[str] | None = None) -> None:
    columns = additional_columns or []
    columns += [k for k, v in properties.items() if v.get('foreign_key')]
    columns += [name for name, prop in properties.items() if prop['scryfall']]
    query = f'INSERT INTO `{table}` ('
    query += ', '.join(columns)
    query += ') VALUES ('
    query += '), ('.join(', '.join(str(sqlescape(entry[column])) for column in columns) for entry in values)
    query += ')'
    db().execute(query)

async def update_bugged_cards_async() -> None:
    bugs = await fetcher.bugged_cards_async()
    if bugs is None:
        return
    db().begin('update_bugged_cards')
    db().execute('DELETE FROM card_bug')
    for bug in bugs:
        last_confirmed_ts = dtutil.parse_to_ts(bug['last_updated'], '%Y-%m-%d %H:%M:%S', dtutil.UTC_TZ)
        name = bug['card'].split(' // ')[0]  # We need a face name from split cards - we don't have combined card names yet.
        card_id = db().value('SELECT card_id FROM face WHERE name = %s', [name])
        if card_id is None:
            print('UNKNOWN BUGGED CARD: {card}'.format(card=bug['card']))
            continue
        db().execute('INSERT INTO card_bug (card_id, description, classification, last_confirmed, url, from_bug_blog, bannable) VALUES (%s, %s, %s, %s, %s, %s, %s)', [card_id, bug['description'], bug['category'], last_confirmed_ts, bug['url'], bug['bug_blog'], bug['bannable']])
    db().commit('update_bugged_cards')

async def update_pd_legality_async() -> None:
    for s in seasons.SEASONS:
        await set_legal_cards_async(season=s)
        if s == seasons.current_season_code():
            break

def single_face_value(p: CardDescription, card_id: int, position: int = 1) -> dict[str, Any]:
    if not card_id:
        raise InvalidDataException(f'Cannot insert a face without a card_id: {p}')
    result: dict[str, Any] = {}
    result['card_id'] = card_id
    result['name'] = p['name']  # always present in scryfall
    result['mana_cost'] = p['mana_cost']  # always present in scryfall
    result['cmc'] = p['cmc']  # always present
    result['power'] = p.get('power')
    result['toughness'] = p.get('toughness')
    result['loyalty'] = p.get('loyalty')
    result['type_line'] = p.get('type_line', '')
    result['oracle_text'] = p.get('oracle_text', '')
    result['hand'] = p.get('hand_modifier')
    result['life'] = p.get('life_modifier')
    result['position'] = position
    return result

def multiple_faces_values(p: CardDescription, card_id: int) -> list[dict[str, Any]]:
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

def meld_face_values(p: CardDescription, cards: dict[str, int]) -> list[dict[str, Any]]:
    values = []
    all_parts = p.get('all_parts')
    if all_parts is None:
        raise InvalidArgumentException(f'Tried to insert_meld_result_faces on a card without all_parts: {p}')
    front_face_names = [part['name'] for part in all_parts if part['component'] == 'meld_part' and part['name'] not in KNOWN_MELDS]
    card_ids = [cards[name] for name in front_face_names]
    for card_id in card_ids:
        values.append(single_face_value(p, card_id, 2))
    return values

def is_meld_result(p: CardDescription) -> bool:
    all_parts = p.get('all_parts')
    if all_parts is None or not p['layout'] == 'meld':
        return False
    meld_result_name = next((part['name'] for part in all_parts if part['component'] == 'meld_result'), None)
    if not meld_result_name:
        # If we can't find the cannonical meld result, fall back to the part with no mana cost
        meld_result_name = next(part['name'] for part in all_parts if part['name'] in KNOWN_MELDS)
    return p['name'] == meld_result_name

def load_sets() -> dict[str, int]:
    return {s['code']: int(s['id']) for s in db().select('SELECT id, code FROM `set`')}

def insert_set(s: Any) -> int:
    sql = 'INSERT INTO `set` ('
    sql += ', '.join(name for name, prop in card.set_properties().items() if prop['scryfall'])  #
    sql += ') VALUES ('
    sql += ', '.join('%s' for name, prop in card.set_properties().items() if prop['scryfall'])
    sql += ')'
    values = [date2int(s.get(database2json(name)), name) for name, prop in card.set_properties().items() if prop['scryfall']]
    db().execute(sql, values)
    return db().last_insert_rowid()

async def update_sets_async() -> dict:
    sets = load_sets()
    for s in await fetcher.all_sets_async():
        if s['code'] not in sets.keys():
            insert_set(s)
    return load_sets()

def printing_value(p: CardDescription, card_id: int, set_id: int, rarity_id: int) -> dict[str, Any]:
    if not card_id or not set_id:
        raise InvalidDataException(f'Cannot insert printing without card_id and set_id: {card_id}, {set_id}, {p}')
    result: dict[str, Any] = {}
    result['card_id'] = card_id
    result['set_id'] = set_id
    result['rarity_id'] = rarity_id
    result['system_id'] = p.get('id')
    result['flavor'] = p.get('flavor_text')
    result['artist'] = p.get('artist')
    result['number'] = p.get('collector_number')
    result['watermark'] = p.get('watermark')
    result['reserved'] = 1 if p.get('reserved') else 0  # replace True and False with 1 and 0
    result['flavor_name'] = p.get('flavor_name')
    return result

async def set_legal_cards_async(season: str | None = None) -> None:
    if season is None:
        season = seasons.current_season_code()

    new_list: set[str] = set()
    try:
        new_list = set(await fetcher.legal_cards_async(season=season))
    except fetcher.FetchException:
        return
    if new_list == set() or new_list is None:
        return

    format_id = get_format_id(f'Penny Dreadful {season}', True)

    if season is not None:
        # Older formats don't change
        populated = db().select('SELECT id from card_legality WHERE format_id = %s LIMIT 1', [format_id])
        if populated:
            return

    print(f'Setting Legal Cards for {season} ({format_id}) - {len(new_list)} cards')

    # In case we get windows line endings.
    new_list = {c.rstrip() for c in new_list}

    db().begin('set_legal_cards')
    db().execute('DELETE FROM card_legality WHERE format_id = %s', [format_id])
    db().execute('SET group_concat_max_len=100000')

    all_cards = db().select(base_query_lite())
    legal_cards = []
    for row in all_cards:
        if row['name'] in new_list:
            legal_cards.append("({format_id}, {card_id}, 'Legal')".format(format_id=format_id,
                                                                          card_id=row['id']))
        elif row['flavor_names']:
            for fn in row['flavor_names'].split('|'):
                if fn in new_list:
                    legal_cards.append("({format_id}, {card_id}, 'Legal')".format(format_id=format_id,
                                                                                  card_id=row['id']))
                    break
    sql = """INSERT INTO card_legality (format_id, card_id, legality)
             VALUES {values}""".format(values=', '.join(legal_cards))

    db().execute(sql)
    db().commit('set_legal_cards')
    # Check we got the right number of legal cards.
    n = db().value('SELECT COUNT(*) FROM card_legality WHERE format_id = %s', [format_id])
    if n != len(new_list):
        print(f'Found {n} pd legal cards in the database but the list was {len(new_list)} long')
        sql = f'SELECT bq.name FROM ({base_query()}) AS bq WHERE bq.id IN (SELECT card_id FROM card_legality WHERE format_id = {format_id})'
        db_legal_list = [row['name'] for row in db().select(sql)]
        print(set(new_list).symmetric_difference(set(db_legal_list)))

def rebuild_cache() -> None:
    db().execute('DROP TABLE IF EXISTS _new_cache_card')
    db().execute('SET group_concat_max_len=100000')
    db().execute(create_table_def('_new_cache_card', card.base_query_properties(), base_query()))
    db().execute('CREATE UNIQUE INDEX idx_u_card_id ON _new_cache_card (card_id)')
    db().execute('CREATE UNIQUE INDEX idx_u_name ON _new_cache_card (name(142))')
    db().execute('CREATE UNIQUE INDEX idx_u_names ON _new_cache_card (names(142))')
    db().execute('DROP TABLE IF EXISTS _old_cache_card')
    db().execute('CREATE TABLE IF NOT EXISTS _cache_card (_ INT)')  # Prevent error in RENAME TABLE below if bootstrapping.
    db().execute('RENAME TABLE _cache_card TO _old_cache_card, _new_cache_card TO _cache_card')
    db().execute('DROP TABLE IF EXISTS _old_cache_card')

def add_to_cache(ids: list[int]) -> None:
    if not ids:
        return
    values = ', '.join([str(id) for id in ids])
    query = base_query(f'c.id IN ({values})')
    sql = f'INSERT INTO _cache_card {query}'
    db().execute(sql)

def database2json(propname: str) -> str:
    if propname == 'system_id':
        propname = 'id'
    return propname

def date2int(s: str, name: str) -> str | float:
    if name == 'released_at':
        return dtutil.parse_to_ts(s, '%Y-%m-%d', dtutil.WOTC_TZ)
    return s

# I'm not sure this belong here, but it's here for now.
def get_format_id(name: str, allow_create: bool = False) -> int:
    if name == 'Penny Dreadful':
        raise InvalidArgumentException('Queried PD without a season')
    if len(FORMAT_IDS) == 0:
        rs = db().select('SELECT id, name FROM format')
        for row in rs:
            FORMAT_IDS[row['name']] = row['id']
    if name not in FORMAT_IDS.keys() and allow_create:
        db().execute('INSERT INTO format (name) VALUES (%s)', [name])
        FORMAT_IDS[name] = db().last_insert_rowid()
    if name not in FORMAT_IDS.keys():
        raise InvalidArgumentException(f'Unknown format: {name}')
    return FORMAT_IDS[name]

def get_format_id_from_season_id(season_id: int) -> int:
    season_code = seasons.SEASONS[int(season_id) - 1]
    format_name = f'Penny Dreadful {season_code}'
    return get_format_id(format_name)

def get_all_cards() -> list[Card]:
    rs = db().select(cached_base_query())
    return [Card(r) for r in rs]

def supertypes(type_line: str) -> list[str]:
    types = type_line.split('-')[0]
    possible_supertypes = ['Basic', 'Legendary', 'Ongoing', 'Snow', 'World']
    sts = []
    for possible in possible_supertypes:
        if possible in types:
            sts.append(possible)
    return sts

def subtypes(type_line: str) -> list[str]:
    if ' - ' not in type_line:
        return []
    return type_line.split(' - ')[1].split(' ')
