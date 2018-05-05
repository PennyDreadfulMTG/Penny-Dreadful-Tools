import hashlib
import json
import time
from typing import Dict, List, Optional, Set

from decksite import deck_name
from decksite.data import guarantee, query
from decksite.data.top import Top
from decksite.database import db
from magic import card, legality, mana, oracle, rotation
from shared import dtutil
from shared.container import Container
from shared.database import sqlescape
from shared.pd_exception import InvalidDataException


# pylint: disable=too-many-instance-attributes
class Deck(Container):
    def __init__(self, params) -> None:
        super().__init__()
        for k in params.keys():
            self[k] = params[k]
        self.sorted = False

    def all_cards(self) -> List[card.Card]:
        cards: List[card.Card] = []
        for entry in self.maindeck + self.sideboard:
            cards += [entry['card']] * entry['n']
        return cards

    def sort(self):
        if not self.sorted and (len(self.maindeck) > 0 or len(self.sideboard) > 0):
            self.maindeck.sort(key=lambda x: oracle.deck_sort(x['card']))
            self.sideboard.sort(key=lambda x: oracle.deck_sort(x['card']))
            self.sorted = True

    def is_in_current_run(self) -> bool:
        if ((self.wins or 0) + (self.draws or 0) + (self.losses or 0) >= 5) or self.retired:
            return False
        elif self.competition_type_name != 'League':
            return False
        elif self.competition_end_date < dtutil.now():
            return False
        return True

    def __str__(self):
        self.sort()
        s = ''
        for entry in self.maindeck:
            s += '{n} {name}\n'.format(n=entry['n'], name=entry['name'])
        s += '\n'
        for entry in self.sideboard:
            s += '{n} {name}\n'.format(n=entry['n'], name=entry['name'])
        return s.strip()

    def is_person_associated(self):
        return self.discord_id is not None

def load_deck(deck_id) -> Deck:
    return guarantee.exactly_one(load_decks('d.id = {deck_id}'.format(deck_id=sqlescape(deck_id))))

def load_season(season_id=None, league_only=False):
    season = Container()
    where = 'TRUE'
    if league_only:
        where = 'd.competition_id IN ({competition_ids_by_type_select})'.format(competition_ids_by_type_select=query.competition_ids_by_type_select('League'))
    season.decks = load_decks(where, season_id=season_id)
    season.number = season_id
    return season

# pylint: disable=attribute-defined-outside-init
def load_decks(where='1 = 1', order_by=None, limit='', season_id=None) -> List[Deck]:
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
            s.name AS source_name,
            IFNULL(a.name, '') AS archetype_name,
            cache.normalized_name AS name,
            cache.colors,
            cache.colored_symbols,
            cache.legal_formats,
            season.id AS season_id,
            IFNULL(MAX(m.date), d.created_date) AS active_date
        FROM
            deck AS d
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
        WHERE ({where}) AND ({season_query})
        GROUP BY
            d.id,
            season.id -- In theory this is not necessary as all decks are in a single season and we join on the date but MySQL cannot work that out so give it the hint it needs.
        ORDER BY
            {order_by}
        {limit}
    """.format(person_query=query.person_query(), competition_join=query.competition_join(), where=where, order_by=order_by, limit=limit, season_query=query.season_query(season_id), season_join=query.season_join())
    db().execute('SET group_concat_max_len=100000')
    rows = db().execute(sql)
    decks = []
    for row in rows:
        d = Deck(row)
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
        decks.append(d)
    load_cards(decks)
    load_competitive_stats(decks)
    return decks

# We ignore 'also' here which means if you are playing a deck where there are no other G or W cards than Kitchen Finks we will claim your deck is neither W nor G which is not true. But this should cover most cases.
# We also ignore split and aftermath cards so if you are genuinely using a color in a split card but have no other cards of that color we won't claim it as one of the deck's colors.
def set_colors(d) -> None:
    deck_colors: Set[str] = set()
    deck_colored_symbols: List[str] = []
    for c in [entry['card'] for entry in d.maindeck + d.sideboard]:
        for cost in c.get('mana_cost') or ():
            if c.layout == 'split' or c.layout == 'aftermath':
                continue # They might only be using one half so ignore it.
            card_symbols = mana.parse(cost)
            card_colors = mana.colors(card_symbols)
            deck_colors.update(card_colors['required'])
            card_colored_symbols = mana.colored_symbols(card_symbols)
            deck_colored_symbols += card_colored_symbols['required']
    d.colors = mana.order(deck_colors)
    d.colored_symbols = deck_colored_symbols

def set_legality(d) -> None:
    d.legal_formats = legality.legal_formats(d)

# Expects:
#
# {
#     'name': <string>,
#     'url': <string>,
#     'source': <string>,
#     'identifier': <string>,
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
def add_deck(params) -> Deck:
    if not params.get('mtgo_username') and not params.get('tappedout_username') and not params.get('mtggoldfish_username'):
        raise InvalidDataException('Did not find a username in {params}'.format(params=params))
    person_id = get_or_insert_person_id(params.get('mtgo_username'), params.get('tappedout_username'), params.get('mtggoldfish_username'))
    deck_id = get_deck_id(params['source'], params['identifier'])
    if deck_id:
        add_cards(deck_id, params['cards'])
        d = load_deck(deck_id)
        prime_cache(d)
        return d
    created_date = params.get('created_date')
    if not created_date:
        created_date = time.time()
    archetype_id = get_archetype_id(params.get('archetype'))
    for result in ['wins', 'losses', 'draws']:
        if params.get('competition_id') and not params.get(result):
            params[result] = 0
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
        reviewed
    ) VALUES (
         IFNULL(%s, UNIX_TIMESTAMP()),  UNIX_TIMESTAMP(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE
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
        params.get('finish')
    ]
    deck_id = db().insert(sql, values)
    add_cards(deck_id, params['cards'])
    d = load_deck(deck_id)
    prime_cache(d)
    return d

def prime_cache(d) -> None:
    set_colors(d)
    colors_s = json.dumps(d.colors)
    colored_symbols_s = json.dumps(d.colored_symbols)
    set_legality(d)
    legal_formats_s = json.dumps(list(d.legal_formats))
    normalized_name = deck_name.normalize(d)
    db().begin()
    db().execute('DELETE FROM deck_cache WHERE deck_id = %s', [d.id])
    db().execute('INSERT INTO deck_cache (deck_id, normalized_name, colors, colored_symbols, legal_formats) VALUES (%s, %s, %s, %s, %s)', [d.id, normalized_name, colors_s, colored_symbols_s, legal_formats_s])
    db().commit()

def add_cards(deck_id, cards) -> None:
    db().begin()
    deckhash = hashlib.sha1(repr(cards).encode('utf-8')).hexdigest()
    db().execute('UPDATE deck SET decklist_hash = %s WHERE id = %s', [deckhash, deck_id])
    db().execute('DELETE FROM deck_card WHERE deck_id = %s', [deck_id])
    for name, n in cards['maindeck'].items():
        insert_deck_card(deck_id, name, n, False)
    for name, n in cards['sideboard'].items():
        insert_deck_card(deck_id, name, n, True)
    db().commit()

def get_deck_id(source_name, identifier) -> Optional[int]:
    source_id = get_source_id(source_name)
    sql = 'SELECT id FROM deck WHERE source_id = %s AND identifier = %s'
    return db().value(sql, [source_id, identifier])

def insert_deck_card(deck_id, name, n, in_sideboard) -> None:
    name = oracle.valid_name(name)
    sql = 'INSERT INTO deck_card (deck_id, card, n, sideboard) VALUES (%s, %s, %s, %s)'
    db().execute(sql, [deck_id, name, n, in_sideboard])

def get_or_insert_person_id(mtgo_username, tappedout_username, mtggoldfish_username) -> int:
    sql = 'SELECT id FROM person WHERE LOWER(mtgo_username) = LOWER(%s) OR LOWER(tappedout_username) = LOWER(%s) OR LOWER(mtggoldfish_username) = LOWER(%s)'
    person_id = db().value(sql, [mtgo_username, tappedout_username, mtggoldfish_username])
    if person_id:
        return person_id
    sql = 'INSERT INTO person (mtgo_username, tappedout_username, mtggoldfish_username) VALUES (%s, %s, %s)'
    return db().insert(sql, [mtgo_username, tappedout_username, mtggoldfish_username])

def get_source_id(source) -> int:
    sql = 'SELECT id FROM source WHERE name = %s'
    source_id = db().value(sql, [source])
    if not source_id:
        raise InvalidDataException('Unknown source: `{source}`'.format(source=source))
    return source_id

def get_archetype_id(archetype) -> Optional[int]:
    sql = 'SELECT id FROM archetype WHERE name = %s'
    return db().value(sql, [archetype])

def load_similar_decks(ds: List[Deck]) -> None:
    threshold = 20
    cards_escaped = ', '.join(sqlescape(name) for name in all_card_names(ds))
    potentially_similar = load_decks('d.id IN (SELECT deck_id FROM deck_card WHERE card IN ({cards_escaped}))'.format(cards_escaped=cards_escaped))
    for d in ds:
        for psd in potentially_similar:
            psd.similarity_score = round(similarity_score(d, psd) * 100)
        d.similar_decks = [psd for psd in potentially_similar if psd.similarity_score >= threshold and psd.id != d.id]
        d.similar_decks.sort(key=lambda d: -(d.similarity_score))

def all_card_names(ds: List[Deck]) -> List[str]:
    basic_lands = ['Plains', 'Island', 'Swamp', 'Mountain', 'Forest']
    names = []
    for d in ds:
        for c in d.maindeck:
            if c['name'] not in basic_lands:
                names.append(c['name'])
    return names

# Dead simple for now, may get more sophisticated. 1 point for each differently named card shared in maindeck. Count irrelevant.
def similarity_score(a: Deck, b: Deck) -> float:
    score = 0
    for c in a.maindeck:
        if c in b.maindeck:
            score += 1
    return float(score) / float(max(len(a.maindeck), len(b.maindeck)))

def load_decks_by_cards(names) -> List[Deck]:
    sql = """
        d.id IN (
            SELECT deck_id
            FROM deck_card
            WHERE card IN ({names})
            GROUP BY deck_id
            HAVING COUNT(DISTINCT card) = {n})
        """.format(n=len(names), names=', '.join(map(sqlescape, names)))
    return load_decks(sql)

def load_cards(decks) -> None:
    if len(decks) == 0:
        return
    decks_by_id = {d.id: d for d in decks}
    cards = oracle.cards_by_name()
    sql = """
        SELECT deck_id, card, n, sideboard FROM deck_card WHERE deck_id IN ({deck_ids})
    """.format(deck_ids=', '.join(map(sqlescape, map(str, decks_by_id.keys()))))
    rs = db().execute(sql)
    for row in rs:
        location = 'sideboard' if row['sideboard'] else 'maindeck'
        name = row['card']
        d = decks_by_id[row['deck_id']]
        d[location] = d.get(location, [])
        d[location].append({'n': row['n'], 'name': name, 'card': cards[name]})

# It makes the main query about 5x faster to do this as a separate query (which is trivial and done only once for all decks).
def load_competitive_stats(decks) -> None:
    if len(decks) == 0:
        return
    decks_by_id = {d.id: d for d in decks}
    if len(decks) < 1000:
        where = 'd.id IN ({deck_ids})'.format(deck_ids=', '.join(map(sqlescape, map(str, decks_by_id.keys()))))
    else:
        where = 'TRUE' # MySQL doesn't like to be asked to do IN queries for very long argument lists. Just load everything. (MariaDB doesn't care, interestingly.)
    sql = """
        SELECT
            d.id,
            SUM(CASE WHEN dm.games > odm.games THEN 1 ELSE 0 END) AS opp_wins,
            SUM(CASE WHEN dm.games < odm.games THEN 1 ELSE 0 END) AS opp_losses,
            SUM(CASE WHEN dm.games = odm.games THEN 1 ELSE 0 END) AS opp_draws,
            ROUND(SUM(CASE WHEN dm.games > odm.games THEN 1 ELSE 0 END) / NULLIF((SUM(CASE WHEN dm.games <> odm.games THEN 1 ELSE 0 END)), 0), 2) * 100 AS omw,
            GROUP_CONCAT(m.elimination) AS elim
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
    rs = db().execute(sql)
    for row in rs:
        if decks_by_id.get(row['id']):
            decks_by_id[row['id']].opp_wins = row['opp_wins']
            decks_by_id[row['id']].opp_losses = row['opp_losses']
            decks_by_id[row['id']].omw = row['omw']
            decks_by_id[row['id']].elim = row['elim'] # This property is never used? and is always a bunch of zeroes?

def count_matches(deck_id: int, opponent_deck_id: int) -> Dict[int, int]:
    sql = 'SELECT deck_id, count(id) as count FROM deck_match WHERE deck_id in (%s, %s) group by deck_id'
    result = {int(deck_id): 0, int(opponent_deck_id): 0}
    for row in db().execute(sql, [deck_id, opponent_deck_id]):
        result[row['deck_id']] = row['count']
    return result

# Query Helpers for number of decks, wins, draws and losses.

def nwdl_select(prefix='', additional_clause='TRUE') -> str:
    return """
        SUM(CASE WHEN {additional_clause} AND d.id IS NOT NULL THEN 1 ELSE 0 END) AS `{prefix}num_decks`,
        SUM(CASE WHEN {additional_clause} THEN wins ELSE 0 END) AS `{prefix}wins`,
        SUM(CASE WHEN {additional_clause} THEN losses ELSE 0 END) AS `{prefix}losses`,
        SUM(CASE WHEN {additional_clause} THEN draws ELSE 0 END) AS `{prefix}draws`,
        SUM(CASE WHEN {additional_clause} AND wins >= 5 AND losses = 0 AND d.source_id IN (SELECT id FROM source WHERE name = 'League') THEN 1 ELSE 0 END) AS {prefix}perfect_runs,
        SUM(CASE WHEN {additional_clause} AND dsum.finish = 1 THEN 1 ELSE 0 END) AS `{prefix}tournament_wins`,
        SUM(CASE WHEN {additional_clause} AND dsum.finish <= 8 THEN 1 ELSE 0 END) AS `{prefix}tournament_top8s`,
        IFNULL(ROUND((SUM(CASE WHEN {additional_clause} THEN wins ELSE 0 END) / NULLIF(SUM(CASE WHEN {additional_clause} THEN wins + losses ELSE 0 END), 0)) * 100, 1), '') AS `{prefix}win_percent`
    """.format(prefix=prefix, additional_clause=additional_clause)

def nwdl_all_select() -> str:
    return nwdl_select('all_')

def nwdl_season_select() -> str:
    return nwdl_select('season_', 'dsum.created_date >= {season_start}'.format(season_start=int(rotation.last_rotation().timestamp())))

def nwdl_week_select() -> str:
    return nwdl_select('week_', 'dsum.created_date >= UNIX_TIMESTAMP(NOW() - INTERVAL 1 WEEK)')

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
