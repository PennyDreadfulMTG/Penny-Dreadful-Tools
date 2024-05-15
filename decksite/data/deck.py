import hashlib
import json
import time
from typing import TypedDict

from decksite import deck_name
from decksite.data import query, season
from decksite.data.top import Top
from decksite.database import db
from magic import legality, mana, oracle, seasons
from magic.colors import find_colors
from magic.models import CardRef, Deck
from shared import dtutil, guarantee, logger
from shared import redis_wrapper as redis
from shared.container import Container
from shared.database import sqlescape
from shared.pd_exception import InvalidDataException


def latest_decks(season_id: str | int | None = None) -> list[Deck]:
    ds, _ = load_decks(where='d.created_date > UNIX_TIMESTAMP(NOW() - INTERVAL 30 DAY)', limit='LIMIT 500', season_id=season_id)
    return ds

def recent_decks_for_person(person_id: int) -> list[Deck]:
    ds, _ = load_decks(where=f'd.person_id = {sqlescape(person_id)}', order_by='active_date DESC', limit='LIMIT 10', season_id=seasons.current_season_num())
    return ds

def load_deck(deck_id: int) -> Deck:
    ds, _ = load_decks(f'd.id = {sqlescape(deck_id)}')
    return guarantee.exactly_one(ds)

def load_decks(where: str = 'TRUE',
               having: str = 'TRUE',
               order_by: str | None = None,
               limit: str = '',
               season_id: str | int | None = None,
               ) -> tuple[list[Deck], int]:
    if not redis.enabled():
        return load_decks_heavy(where, having, order_by, limit, season_id)
    columns = """
        d.id,
        d.finish,
        d.decklist_hash,
        cache.active_date,
        cache.wins,
        cache.losses,
        cache.draws,
        cache.color_sort,
        ct.name AS competition_type_name,
        COUNT(*) OVER () AS total
    """
    group_by = """
            d.id,
            d.competition_id, -- Every deck has only one competition_id but if we want to use competition_id in the HAVING clause we need this.
            season.season_id -- In theory this is not necessary as all decks are in a single season and we join on the date but MySQL cannot work that out so give it the hint it needs.
    """
    sql = load_decks_query(columns, where=where, group_by=group_by, having=having, order_by=order_by, limit=limit, season_id=season_id)
    db().execute('SET group_concat_max_len=100000')
    rows = db().select(sql)
    decks_by_id = {}
    heavy = []
    for row in rows:
        d = redis.get_container('decksite:deck:{id}'.format(id=row['id']))
        if d is None or d.name is None:
            heavy.append(row['id'])
        else:
            decks_by_id[row['id']] = deserialize_deck(d)
    if heavy:
        where = 'd.id IN ({deck_ids})'.format(deck_ids=', '.join(map(sqlescape, map(str, heavy))))
        loaded_decks, _ = load_decks_heavy(where)
        for d in loaded_decks:
            decks_by_id[d.id] = d
    decks = []
    for row in rows:
        decks.append(decks_by_id[row['id']])
    return decks, 0 if not rows else rows[0]['total']

def load_decks_query(columns: str,
                     where: str = 'TRUE',
                     group_by: str | None = None,
                     having: str = 'TRUE',
                     order_by: str | None = None,
                     limit: str = '',
                     season_id: str | int | None = None,
                     ) -> str:
    if order_by is None:
        order_by = 'active_date DESC, d.finish IS NULL, d.finish'
    if group_by is None:
        group_by = ''
    else:
        group_by = f'GROUP BY {group_by}'
    sql = """
        SELECT
            {columns}
        FROM
            deck AS d
        """
    if 'p.' in where or 'p.' in order_by:
        sql += """
        LEFT JOIN
            person AS p ON d.person_id = p.id
        """
    if 's.' in where or 's.' in order_by:
        sql += """
        LEFT JOIN
            source AS s ON d.source_id = s.id
        """
    if 'a.' in where or 'a.' in order_by:
        sql += """
        LEFT JOIN
            archetype AS a ON d.archetype_id = a.id
        """
    if 'q.' in where or 'q.' in order_by:
        sql += """
        LEFT JOIN
            deck_archetype_change AS q ON q.deck_id = d.id
        """
    sql += """
        {competition_join}
        LEFT JOIN
            deck_cache AS cache ON d.id = cache.deck_id
        {season_join}
        WHERE
            ({where}) AND ({season_query})
        {group_by}
        HAVING
            {having}
        ORDER BY
            {order_by}
        {limit}
    """
    sql = sql.format(columns=columns, person_query=query.person_query(), competition_join=query.competition_join(), season_query=query.season_query(season_id, 'season.season_id'), season_join=query.season_join(), where=where, group_by=group_by, having=having, order_by=order_by, limit=limit)
    return sql

def deserialize_deck(sdeck: Container) -> Deck:
    deck = Deck(sdeck)
    deck.active_date = dtutil.ts2dt(deck.active_date)
    deck.created_date = dtutil.ts2dt(deck.created_date)
    deck.updated_date = dtutil.ts2dt(deck.updated_date)
    if deck.competition_end_date is not None:
        deck.competition_end_date = dtutil.ts2dt(deck.competition_end_date)
    deck.wins = int(deck.wins)
    deck.losses = int(deck.losses)
    deck.draws = int(deck.draws)
    if deck.get('omw') is not None:
        deck.omw = float(deck.omw)
    deck.maindeck = [CardRef(ref['name'], ref['n']) for ref in deck.maindeck]
    deck.sideboard = [CardRef(ref['name'], ref['n']) for ref in deck.sideboard]
    return deck

def load_decks_heavy(where: str = 'TRUE',
                     having: str = 'TRUE',
                     order_by: str | None = None,
                     limit: str = '',
                     season_id: str | int | None = None,
                     ) -> tuple[list[Deck], int]:
    if order_by is None:
        order_by = 'active_date DESC, d.finish IS NULL, d.finish'

    sql = """
        SELECT
            d.id,
            d.name AS original_name,
            d.created_date,
            d.updated_date,
            SUM(CASE WHEN dm.games > IFNULL(odm.games, 0) THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN dm.games < odm.games THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN dm.games = odm.games THEN 1 ELSE 0 END) AS draws,
            d.finish,
            d.archetype_id,
            d.url AS source_url,
            d.competition_id,
            c.name AS competition_name,
            c.end_date AS competition_end_date,
            c.top_n AS competition_top_n,
            ct.name AS competition_type_name,
            d.identifier,
            {person_query} AS person,
            p.id AS person_id,
            p.banned,
            p.discord_id,
            d.decklist_hash,
            d.retired,
            d.reviewed,
            s.name AS source_name,
            IFNULL(a.name, '') AS archetype_name,
            cache.normalized_name AS name,
            cache.colors,
            cache.colored_symbols,
            cache.color_sort,
            cache.legal_formats,
            ROUND(cache.omw * 100, 2) AS omw,
            season.season_id,
            IFNULL(MAX(m.date), d.created_date) AS active_date,
            COUNT(*) OVER () AS total
--            MAX(q.changed_date) AS last_archetype_change
        FROM
            deck AS d
--        LEFT JOIN
--            deck_archetype_change AS q ON q.deck_id = d.id
        LEFT JOIN
            person AS p ON d.person_id = p.id
        LEFT JOIN
            source AS s ON d.source_id = s.id
        LEFT JOIN
            archetype AS a ON d.archetype_id = a.id
        {competition_join}
        LEFT JOIN
            deck_cache AS cache ON d.id = cache.deck_id
        LEFT JOIN
            deck_match AS dm ON d.id = dm.deck_id
        LEFT JOIN
            `match` AS m ON dm.match_id = m.id
        LEFT JOIN
            deck_match AS odm ON odm.deck_id <> d.id AND dm.match_id = odm.match_id
        {season_join}
        WHERE
            ({where}) AND ({season_query})
        GROUP BY
            d.id,
            d.competition_id, -- Every deck has only one competition_id but if we want to use competition_id in the HAVING clause we need this.
            season.season_id -- In theory this is not necessary as all decks are in a single season and we join on the date but MySQL cannot work that out so give it the hint it needs.
        HAVING
            {having}
        ORDER BY
            {order_by}
        {limit}
    """.format(person_query=query.person_query(), competition_join=query.competition_join(), season_join=query.season_join(), where=where, season_query=query.season_query(season_id, 'season.season_id'), having=having, order_by=order_by, limit=limit)
    db().execute('SET group_concat_max_len=100000')
    rows = db().select(sql)
    decks = []
    for row in rows:
        d = Deck({k: v for k, v in row.items() if k != 'total'})
        d.maindeck = []
        d.sideboard = []
        d.competition_top_n = Top(d.competition_top_n or 0)
        d.colored_symbols = json.loads(d.colored_symbols or '[]')
        d.colors = json.loads(d.colors or '[]')
        d.legal_formats = set(json.loads(d.legal_formats or '[]'))
        d.active_date = dtutil.ts2dt(d.active_date)
        d.created_date = dtutil.ts2dt(d.created_date)
        d.updated_date = dtutil.ts2dt(d.updated_date)
        if d.competition_end_date:
            d.competition_end_date = dtutil.ts2dt(d.competition_end_date)
        d.can_draw = 'Divine Intervention' in [card.name for card in d.all_cards()]
        d.wins = int(d.wins)
        d.losses = int(d.losses)
        d.draws = int(d.draws)
        decks.append(d)
    load_cards(decks)
    load_competitive_stats(decks)
    for d in decks:
        expiry = 60 if d.is_in_current_run() else 3600
        redis.store(f'decksite:deck:{d.id}', d, ex=expiry)
    return decks, 0 if not rows else rows[0]['total']

# We ignore 'also' here which means if you are playing a deck where there are no other G or W cards than Kitchen Finks we will claim your deck is neither W nor G which is not true. But this should cover most cases.
# We also ignore split and aftermath cards so if you are genuinely using a color in a split card but have no other cards of that color we won't claim it as one of the deck's colors.
def set_colors(d: Deck) -> None:
    d.colors, d.colored_symbols = find_colors([entry.card for entry in d.maindeck + d.sideboard])

def set_legality(d: Deck) -> None:
    d.legal_formats = legality.legal_formats(d)


CardsDescription = dict[str, dict[str, int]]
class RawDeckDescription(TypedDict, total=False):
    name: str  # Name of Deck
    url: str  # Source URL of Deck
    source: str  # Source name
    identifier: str  # Unique ID
    cards: CardsDescription  # Contents of Deck
    archetype: str | None
    created_date: float  # Date deck was created.  If null, current time will be used.
    # One of these three usernames is required:
    mtgo_username: str | None
    tappedout_username: str | None
    mtggoldfish_username: str | None
    # TappedOut Variables
    resource_uri: str | None
    featured_card: str | None
    score: int | None
    thumbnail_url: str | None
    small_thumbnail_url: str | None
    slug: str | None
    user: str | None  # This is mapped to tappedout_username
    # Competition variables (League/Gatherling)
    competition_id: int | None
    finish: int | None
    wins: int
    losses: int
    draws: int
# Expects:
#
# {
#     'name': <str>,
#     'url': <str>,
#     'source': <str>,
#     'identifier': <str>,
#     'cards' {
#         'maindeck': {
#             '<canonical card name>': <int>,
#             …
#         },
#         'sideboard': {
#             '<canonical card name>': <int>,
#             …
#         }
#     }
# }
# Plus one of: mtgo_username OR tappedout_username OR mtggoldfish_username
# Optionally: created_date (unix timestamp, defaults to now), resource_uri, featured_card, score, thumbnail_url, small_thumbnail_url, wins, losses, draws, finish
#
# source + identifier must be unique for each decklist.
def add_deck(params: RawDeckDescription) -> Deck:
    if not params.get('mtgo_username') and not params.get('tappedout_username') and not params.get('mtggoldfish_username'):
        raise InvalidDataException(f'Did not find a username in {params}')
    person_id = get_or_insert_person_id(params.get('mtgo_username'), params.get('tappedout_username'), params.get('mtggoldfish_username'))
    deck_id = get_deck_id(params['source'], params['identifier'])
    cards = params['cards']
    if deck_id:
        db().begin('replace_deck_cards')
        db().execute('UPDATE deck SET decklist_hash = %s WHERE id = %s', [get_deckhash(cards), deck_id])
        db().execute('DELETE FROM deck_card WHERE deck_id = %s', [deck_id])
        add_cards(deck_id, cards)
        db().commit('replace_deck_cards')
        d = load_deck(deck_id)
        prime_cache(d)
        return d
    created_date = params.get('created_date')
    if not created_date:
        created_date = time.time()
    archetype_id = get_archetype_id(params.get('archetype'))
    for result in ['wins', 'losses', 'draws']:
        if params.get('competition_id') and not params.get(result):
            params[result] = 0  # type: ignore
    sql = """INSERT INTO deck (
        created_date,
        updated_date,
        person_id,
        source_id,
        url,
        identifier,
        name,
        competition_id,
        archetype_id,
        resource_uri,
        featured_card,
        score,
        thumbnail_url,
        small_thumbnail_url,
        finish,
        decklist_hash,
        reviewed
    ) VALUES (
         IFNULL(%s, UNIX_TIMESTAMP()), UNIX_TIMESTAMP(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE
    )"""
    values = [
        created_date,
        person_id,
        get_source_id(params['source']),
        params['url'],
        params['identifier'],
        params['name'],
        params.get('competition_id'),
        archetype_id,
        params.get('resource_uri'),
        params.get('featured_card'),
        params.get('score'),
        params.get('thumbnail_url'),
        params.get('small_thumbnail_url'),
        params.get('finish'),
        get_deckhash(cards),
    ]
    db().begin('add_deck')
    deck_id = db().insert(sql, values)
    add_cards(deck_id, cards)
    d = load_deck(deck_id)
    prime_cache(d)
    db().commit('add_deck')
    return d

def prime_cache(d: Deck) -> None:
    set_colors(d)
    colors_s = json.dumps(d.colors)
    colored_symbols_s = json.dumps(d.colored_symbols)
    color_sort = mana.sort_score(d.colors)
    set_legality(d)
    season_id = season.get_season_id(d.created_date)
    # Populate season_id now that we know it because deck_name.normalize uses it.
    d.season_id = season_id
    legal_formats_s = json.dumps(list(d.legal_formats))
    normalized_name = deck_name.normalize(d)
    # If this is a new deck we're going to make a new record. If it's an existing deck we might as well update a few things that might have changed implementation but should otherwise be static. But leave wins/draws/losses/active date alone.
    sql = """
        INSERT INTO
            deck_cache (deck_id, normalized_name, colors, colored_symbols, color_sort, legal_formats, wins, draws, losses, active_date, season_id)
        VALUES
            (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE normalized_name = %s, colors = %s, colored_symbols = %s, color_sort = %s, legal_formats = %s, season_id = %s
    """
    db().execute(sql, [d.id, normalized_name, colors_s, colored_symbols_s, color_sort, legal_formats_s, 0, 0, 0, dtutil.dt2ts(d.created_date), season_id, normalized_name, colors_s, colored_symbols_s, color_sort, legal_formats_s, season_id])
    # If it was worth priming the in-db cache it's worth busting the in-memory cache to pick up the changes.
    redis.clear(f'decksite:deck:{d.id}')

def add_cards(deck_id: int, cards: CardsDescription) -> None:
    try:
        db().begin('add_cards')
        for name, n in cards.get('maindeck', {}).items():
            insert_deck_card(deck_id, name, n, False)
        for name, n in cards.get('sideboard', {}).items():
            insert_deck_card(deck_id, name, n, True)
        db().commit('add_cards')
    except InvalidDataException as e:
        logger.warning('Unable to add_cards to {deck_id} with {cards}', e)
        db().rollback('add_cards')
        raise

def get_deck_id(source_name: str, identifier: str) -> int | None:
    source_id = get_source_id(source_name)
    sql = 'SELECT id FROM deck WHERE source_id = %s AND identifier = %s'
    return db().value(sql, [source_id, identifier])

def insert_deck_card(deck_id: int, name: str, n: int, in_sideboard: bool) -> None:
    name = oracle.valid_name(name)
    sql = 'INSERT INTO deck_card (deck_id, card, n, sideboard) VALUES (%s, %s, %s, %s)'
    db().execute(sql, [deck_id, name, n, in_sideboard])

def get_or_insert_person_id(mtgo_username: str | None, tappedout_username: str | None, mtggoldfish_username: str | None) -> int:
    sql = 'SELECT id FROM person WHERE LOWER(mtgo_username) = LOWER(%s) OR LOWER(tappedout_username) = LOWER(%s) OR LOWER(mtggoldfish_username) = LOWER(%s)'
    person_id = db().value(sql, [mtgo_username, tappedout_username, mtggoldfish_username])
    if person_id:
        return person_id
    sql = 'INSERT INTO person (mtgo_username, tappedout_username, mtggoldfish_username) VALUES (%s, %s, %s)'
    return db().insert(sql, [mtgo_username, tappedout_username, mtggoldfish_username])

def get_source_id(source: str) -> int:
    sql = 'SELECT id FROM source WHERE name = %s'
    source_id = db().value(sql, [source])
    if not source_id:
        raise InvalidDataException(f'Unknown source: `{source}`')
    return source_id

def get_archetype_id(archetype: str | None) -> int | None:
    sql = 'SELECT id FROM archetype WHERE name = %s'
    return db().value(sql, [archetype])

def calculate_similar_decks(ds: list[Deck]) -> None:
    threshold = 20
    cards_escaped = ', '.join(sqlescape(name) for name in all_card_names(ds))
    if not cards_escaped:
        for d in ds:
            d.similar_decks = []
        return
    potentially_similar, _ = load_decks(f'd.id IN (SELECT deck_id FROM deck_card WHERE card IN ({cards_escaped}))')
    for d in ds:
        for psd in potentially_similar:
            psd.similarity_score = round(similarity_score(d, psd) * 100)
        d.similar_decks = [psd for psd in potentially_similar if psd.similarity_score >= threshold and psd.id != d.id]
        d.similar_decks.sort(key=lambda d: -(d.similarity_score))
        redis.store(f'decksite:deck:{d.id}:similar', d.similar_decks, ex=172800)

def all_card_names(ds: list[Deck]) -> set[str]:
    basic_lands = ['Plains', 'Island', 'Swamp', 'Mountain', 'Forest']
    names = set()
    for d in ds:
        for c in d.maindeck:
            if c['name'] not in basic_lands and c['name']:
                names.add(c['name'])
    return names

# Dead simple for now, may get more sophisticated. 1 point for each differently named card shared in maindeck. Count irrelevant.
def similarity_score(a: Deck, b: Deck) -> float:
    score = 0
    for c in a.maindeck:
        if c in b.maindeck:
            score += 1
    return float(score) / float(max(len(a.maindeck), len(b.maindeck)))

def load_decks_by_cards(names: list[str], not_names: list[str]) -> list[Deck]:
    sql = ''
    if names:
        sql += contains_cards_clause(names)
    if names and not_names:
        sql += ' AND '
    if not_names:
        sql += contains_cards_clause(not_names, True)
    ds, _ = load_decks(sql)
    return ds

def contains_cards_clause(names: list[str], negate: bool = False) -> str:
    negation = ' NOT' if negate else ''
    operator = '>=' if negate else '='
    n = 1 if negate else len(names)
    return """d.id {negation} IN (
            SELECT deck_id
            FROM deck_card
            WHERE card IN ({names})
            GROUP BY deck_id
            HAVING COUNT(DISTINCT card) {operator} {n})
        """.format(negation=negation, names=', '.join(map(sqlescape, names)), operator=operator, n=n)

def load_cards(decks: list[Deck]) -> None:
    if len(decks) == 0:
        return
    decks_by_id = {d.id: d for d in decks}
    sql = """
        SELECT deck_id, card, n, sideboard FROM deck_card WHERE deck_id IN ({deck_ids})
    """.format(deck_ids=', '.join(map(sqlescape, map(str, decks_by_id.keys()))))
    rs = db().select(sql)
    for row in rs:
        location = 'sideboard' if row['sideboard'] else 'maindeck'
        name = row['card']
        d = decks_by_id[row['deck_id']]
        d[location] = d.get(location, [])
        d[location].append(CardRef(name, row['n']))

def load_conflicted_decks() -> list[Deck]:
    where = """d.decklist_hash in
        (
            SELECT
                d1.decklist_hash as hash
            FROM
                deck as d1
            INNER JOIN
                deck as d2
            ON
                d1.decklist_hash = d2.decklist_hash AND d1.id <> d2.id AND d1.archetype_id <> d2.archetype_id
            GROUP BY
                d1.decklist_hash
        )"""
    ds, _ = load_decks(where, order_by='d.decklist_hash')
    return ds

def load_queue_similarity(decks: list[Deck]) -> None:
    sql = 'SELECT deck.id, deck_cache.similarity FROM deck JOIN deck_cache ON deck.id = deck_cache.deck_id WHERE NOT deck.reviewed'
    sim = {}
    for row in (Container(r) for r in db().select(sql)):
        sim[row.id] = row.similarity
    for deck in decks:
        deck.similarity = f'{sim[deck.id]}%' if sim[deck.id] is not None else ''

# It makes the main query about 5x faster to do this as a separate query (which is trivial and done only once for all decks).
def load_competitive_stats(decks: list[Deck]) -> None:
    decks_by_id = {d.id: d for d in decks if d.get('omw') is None}
    if len(decks_by_id) == 0:
        return
    if len(decks_by_id) < 1000:
        where = 'd.id IN ({deck_ids})'.format(deck_ids=', '.join(map(sqlescape, map(str, decks_by_id.keys()))))
    else:
        where = 'TRUE'  # MySQL doesn't like to be asked to do IN queries for very long argument lists. Just load everything. (MariaDB doesn't care, interestingly.)
    sql = """
        SELECT
            d.id,
            ROUND(SUM(CASE WHEN dm.games > odm.games THEN 1 ELSE 0 END) / NULLIF((SUM(CASE WHEN dm.games <> odm.games THEN 1 ELSE 0 END)), 0), 2) * 100 AS omw
        FROM
            deck AS d
        INNER JOIN
            deck_match AS my_dm ON my_dm.deck_id = d.id
        LEFT JOIN
            deck_match AS my_odm ON my_odm.match_id = my_dm.match_id AND my_odm.deck_id <> d.id
        INNER JOIN
            deck AS od ON od.id = my_odm.deck_id
        INNER JOIN
            deck_match AS dm ON dm.deck_id = od.id
        LEFT JOIN
            deck_match AS odm ON odm.match_id = dm.match_id AND odm.deck_id <> dm.deck_id
        INNER JOIN
            `match` AS m ON m.id = dm.match_id
        WHERE
            {where}
        GROUP BY
            d.id
    """.format(where=where)
    rs = db().select(sql)
    for row in rs:
        if decks_by_id.get(row['id']):
            decks_by_id[row['id']].omw = row['omw']

def preaggregate() -> None:
    preaggregate_omw()

def preaggregate_omw() -> None:
    sql = """
        UPDATE
            deck_cache AS dc
        INNER JOIN
            (
                SELECT
                    d.id AS deck_id,
                    ROUND(SUM(CASE WHEN dm.games > odm.games THEN 1 ELSE 0 END) / NULLIF((SUM(CASE WHEN dm.games <> odm.games THEN 1 ELSE 0 END)), 0), 2) AS omw
                FROM
                    deck AS d
                INNER JOIN
                    deck_match AS my_dm ON my_dm.deck_id = d.id
                LEFT JOIN
                    deck_match AS my_odm ON my_odm.match_id = my_dm.match_id AND my_odm.deck_id <> d.id
                INNER JOIN
                    deck AS od ON od.id = my_odm.deck_id
                INNER JOIN
                    deck_match AS dm ON dm.deck_id = od.id
                LEFT JOIN
                    deck_match AS odm ON odm.match_id = dm.match_id AND odm.deck_id <> dm.deck_id
                INNER JOIN
                    `match` AS m ON m.id = dm.match_id
                WHERE
                    d.competition_id NOT IN (SELECT id FROM competition WHERE end_date > UNIX_TIMESTAMP(NOW()))
                GROUP BY
                    d.id
            ) AS ds ON dc.deck_id = ds.deck_id
        SET
            dc.omw = ds.omw
    """
    db().execute(sql)

def count_matches(deck_id: int, opponent_deck_id: int) -> dict[int, int]:
    sql = 'SELECT deck_id, count(id) as count FROM deck_match WHERE deck_id in (%s, %s) group by deck_id'
    result = {int(deck_id): 0, int(opponent_deck_id): 0}
    for row in db().select(sql, [deck_id, opponent_deck_id]):
        result[row['deck_id']] = row['count']
    return result

def nwdl_join() -> str:
    return """
        LEFT JOIN
            (
                SELECT
                    d.id,
                    d.created_date,
                    d.finish,
                    SUM(CASE WHEN dm.games > IFNULL(odm.games, 0) THEN 1 ELSE 0 END) AS wins, -- IFNULL so we still count byes as wins.
                    SUM(CASE WHEN dm.games < odm.games THEN 1 ELSE 0 END) AS losses,
                    SUM(CASE WHEN dm.games = odm.games THEN 1 ELSE 0 END) AS draws
                FROM
                    deck_match AS dm
                INNER JOIN
                    deck_match AS odm ON dm.match_id = odm.match_id AND dm.deck_id <> odm.deck_id
                INNER JOIN
                    deck AS d ON d.id = dm.deck_id
                GROUP BY
                    d.id
            ) AS dsum ON d.id = dsum.id
    """

def num_decks(deck_query: str = 'TRUE') -> int:
    sql = f'SELECT COUNT(id) AS c FROM deck WHERE {deck_query}'
    return db().value(sql)


def get_deckhash(cards: CardsDescription) -> str:
    return hashlib.sha1(repr(cards).encode('utf-8')).hexdigest()
