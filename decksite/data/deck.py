import hashlib
import json
import time

from magic import mana, oracle, legality
from shared import dtutil
from shared.container import Container
from shared.database import sqlescape
from shared.pd_exception import InvalidDataException

from decksite import deck_name
from decksite.data import guarantee, query
from decksite.database import db

def latest_decks():
    return load_decks(limit='LIMIT 500')

def load_deck(deck_id):
    return guarantee.exactly_one(load_decks('d.id = {deck_id}'.format(deck_id=sqlescape(deck_id))))

def load_season(season=None, league_only=False):
    if season is None:
        where = 'start. start_date <= UNIX_TIMESTAMP() AND `end`.start_date > UNIX_TIMESTAMP()'
    else:
        try:
            number = int(season)
            code = "'{season}'".format(season=season)
        except ValueError:
            number = 0
            code = sqlescape(season)
        where = 'start.`number` = {number} OR start.`code` = {code}'.format(number=number, code=code)
    sql = """
        SELECT start.`number`, start.`code`, `start`.start_date, `end`.start_date AS end_date
        FROM season AS `start`
        LEFT JOIN season AS `end`
        ON `start`.`number` + 1 = `end`.`number`
        WHERE {where}
    """.format(where=where)
    season = Container(guarantee.exactly_one(db().execute(sql)))
    where = 'd.created_date >= {start_ts} AND d.created_date < IFNULL({end_ts}, 999999999999)'.format(start_ts=season.start_date, end_ts=season.end_date)
    if league_only:
        where = "{where} AND d.competition_id IN (SELECT id FROM competition WHERE competition_type_id IN (SELECT id FROM competition_type WHERE name = 'League'))".format(where=where)
    season.decks = load_decks(where)
    season.start_date = dtutil.ts2dt(season.start_date)
    season.end_date = dtutil.ts2dt(season.end_date)
    return season

# pylint: disable=attribute-defined-outside-init
def load_decks(where='1 = 1', order_by=None, limit=''):
    if order_by is None:
        order_by = 'd.created_date DESC, IFNULL(d.finish, 9999999999)'
    sql = """
        SELECT d.id, d.name AS original_name, d.created_date, d.updated_date, d.wins, d.losses, d.draws, d.finish, d.archetype_id, d.url AS source_url,
            d.competition_id, c.name AS competition_name, c.end_date AS competition_end_date, ct.name AS competition_type_name, d.identifier,
            {person_query} AS person, p.id AS person_id,
            d.created_date AS `date`, d.decklist_hash, d.retired,
            s.name AS source_name, IFNULL(a.name, '') AS archetype_name,
            cache.normalized_name AS name, cache.colors, cache.colored_symbols, cache.legal_formats
        FROM deck AS d
        INNER JOIN person AS p ON d.person_id = p.id
        LEFT JOIN competition AS c ON d.competition_id = c.id
        INNER JOIN source AS s ON d.source_id = s.id
        LEFT JOIN archetype AS a ON d.archetype_id = a.id
        LEFT JOIN deck AS opp ON opp.id IN (SELECT deck_id FROM deck_match WHERE deck_id <> d.id AND match_id IN (SELECT match_id FROM deck_match WHERE deck_id = d.id))
        LEFT JOIN competition_type AS ct ON ct.id = c.competition_type_id
        LEFT JOIN deck_cache AS cache ON d.id = cache.deck_id
        WHERE {where}
        GROUP BY d.id
        ORDER BY {order_by}
        {limit}
    """.format(person_query=query.person_query(), where=where, order_by=order_by, limit=limit)
    db().execute('SET group_concat_max_len=100000')
    rows = db().execute(sql)
    decks = []
    for row in rows:
        d = Deck(row)
        d.maindeck = []
        d.sideboard = []
        d.colored_symbols = json.loads(d.colored_symbols or '[]')
        d.colors = json.loads(d.colors or '[]')
        d.legal_formats = set(json.loads(d.legal_formats or '[]'))
        d.created_date = dtutil.ts2dt(d.created_date)
        d.updated_date = dtutil.ts2dt(d.updated_date)
        if d.competition_end_date:
            d.competition_end_date = dtutil.ts2dt(d.competition_end_date)
        d.date = dtutil.ts2dt(d.date)
        d.can_draw = 'Divine Intervention' in [card.name for card in d.all_cards()]
        decks.append(d)
    load_cards(decks)
    load_opponent_stats(decks)
    return decks

# We ignore 'also' here which means if you are playing a deck where there are no other G or W cards than Kitchen Finks we will claim your deck is neither W nor G which is not true. But this should cover most cases.
# We also ignore split and aftermath cards so if you are genuinely using a color in a split card but have no other cards of that color we won't claim it as one of the deck's colors.
def set_colors(d):
    deck_colors = set()
    deck_colored_symbols = []
    for card in [c['card'] for c in d.maindeck + d.sideboard]:
        for cost in card.get('mana_cost') or ():
            if card.layout == 'split' or card.layout == 'aftermath':
                continue # They might only be using one half so ignore it.
            card_symbols = mana.parse(cost)
            card_colors = mana.colors(card_symbols)
            deck_colors.update(card_colors['required'])
            card_colored_symbols = mana.colored_symbols(card_symbols)
            deck_colored_symbols += card_colored_symbols['required']
    d.colors = mana.order(deck_colors)
    d.colored_symbols = deck_colored_symbols

def set_legality(d):
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
#             ...
#         },
#         'sideboard': {
#             '<canonical card name>': <int>,
#             ...
#         }
#     }
# }
# Plus one of: mtgo_username OR tappedout_username OR mtggoldfish_username
# Optionally: created_date (unix timestamp, defaults to now), resource_uri, featured_card, score, thumbnail_url, small_thumbnail_url, wins, losses, draws, finish
#
# source + identifier must be unique for each decklist.
def add_deck(params):
    if not params.get('mtgo_username') and not params.get('tappedout_username') and not params.get('mtggoldfish_username'):
        raise InvalidDataException('Did not find a username in {params}'.format(params=params))
    person_id = get_or_insert_person_id(params.get('mtgo_username'), params.get('tappedout_username'), params.get('mtggoldfish_username'))
    deck_id = get_deck_id(params['source'], params['identifier'])
    if deck_id:
        add_cards(deck_id, params['cards'])
        return deck_id
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
        wins,
        losses,
        draws,
        finish,
        reviewed
    ) VALUES (
         IFNULL(%s, UNIX_TIMESTAMP()),  UNIX_TIMESTAMP(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE
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
        params.get('wins'),
        params.get('losses'),
        params.get('draws'),
        params.get('finish')
    ]
    deck_id = db().insert(sql, values)
    add_cards(deck_id, params['cards'])
    d = load_deck(deck_id)
    prime_cache(d)
    return d

def prime_cache(d):
    set_colors(d)
    colors_s = json.dumps(d.colors)
    colored_symbols_s = json.dumps(d.colored_symbols)
    set_legality(d)
    legal_formats_s = json.dumps(list(d.legal_formats))
    normalized_name = deck_name.normalize(d)
    db().begin()
    db().execute('DELETE FROM deck_cache WHERE deck_id = ?', [d.id])
    db().execute('INSERT INTO deck_cache (deck_id, normalized_name, colors, colored_symbols, legal_formats) VALUES (?, ?, ?, ?, ?)', [d.id, normalized_name, colors_s, colored_symbols_s, legal_formats_s])
    db().commit()

def add_cards(deck_id, cards):
    db().begin()
    deckhash = hashlib.sha1(repr(cards).encode('utf-8')).hexdigest()
    db().execute("UPDATE deck SET decklist_hash = %s WHERE id = %s", [deckhash, deck_id])
    db().execute("DELETE FROM deck_card WHERE deck_id = %s", [deck_id])
    for name, n in cards['maindeck'].items():
        insert_deck_card(deck_id, name, n, False)
    for name, n in cards['sideboard'].items():
        insert_deck_card(deck_id, name, n, True)
    db().commit()

def get_deck_id(source_name, identifier):
    source_id = get_source_id(source_name)
    sql = 'SELECT id FROM deck WHERE source_id = %s AND identifier = %s'
    return db().value(sql, [source_id, identifier])

def insert_deck_card(deck_id, name, n, in_sideboard):
    card = oracle.valid_name(name)
    sql = 'INSERT INTO deck_card (deck_id, card, n, sideboard) VALUES (%s, %s, %s, %s)'
    return db().execute(sql, [deck_id, card, n, in_sideboard])

def get_or_insert_person_id(mtgo_username, tappedout_username, mtggoldfish_username):
    sql = 'SELECT id FROM person WHERE LOWER(mtgo_username) = LOWER(%s) OR LOWER(tappedout_username) = LOWER(%s) OR LOWER(mtggoldfish_username) = LOWER(%s)'
    person_id = db().value(sql, [mtgo_username, tappedout_username, mtggoldfish_username])
    if person_id:
        return person_id
    sql = 'INSERT INTO person (mtgo_username, tappedout_username, mtggoldfish_username) VALUES (%s, %s, %s)'
    return db().insert(sql, [mtgo_username, tappedout_username, mtggoldfish_username])

def get_source_id(source):
    sql = 'SELECT id FROM source WHERE name = %s'
    source_id = db().value(sql, [source])
    if not source_id:
        raise InvalidDataException('Unknown source: `{source}`'.format(source=source))
    return source_id

def get_archetype_id(archetype):
    sql = 'SELECT id FROM archetype WHERE name = %s'
    return db().value(sql, [archetype])

def get_similar_decks(deck):
    threshold = 20
    cards_escaped = ', '.join(sqlescape(c['name']) for c in deck.maindeck if c['name'] not in ['Plains', 'Island', 'Swamp', 'Mountain', 'Forest'])
    if len(cards_escaped) == 0:
        return []
    decks = load_decks('d.id IN (SELECT deck_id FROM deck_card WHERE card IN ({cards_escaped}))'.format(cards_escaped=cards_escaped))
    for d in decks:
        d.similarity_score = round(similarity_score(deck, d) * 100)
    decks = [d for d in decks if d.similarity_score >= threshold and d.id != deck.id]
    decks.sort(key=lambda d: -(d.similarity_score))
    return decks

# Dead simple for now, may get more sophisticated. 1 point for each differently named card shared in maindeck. Count irrelevant.
def similarity_score(a, b):
    score = 0
    for card in a.maindeck:
        if card in b.maindeck:
            score += 1
    return float(score) / float(max(len(a.maindeck), len(b.maindeck)))

# pylint: disable=too-many-arguments
def insert_match(dt, left_id, left_games, right_id, right_games, round_num=None, elimination=False):
    match_id = db().insert("INSERT INTO `match` (`date`, `round`, elimination) VALUES (%s, %s, %s)", [dtutil.dt2ts(dt), round_num, elimination])
    sql = 'INSERT INTO deck_match (deck_id, match_id, games) VALUES (%s, %s, %s)'
    db().execute(sql, [left_id, match_id, left_games])
    if right_id is not None: # Don't insert matches for the bye.
        db().execute(sql, [right_id, match_id, right_games])
    return match_id

def get_matches(d, should_load_decks=False):
    sql = """
        SELECT
            m.`date`, m.id, m.round, m.elimination,
            dm1.games AS game_wins,
            dm2.deck_id AS opponent_deck_id, IFNULL(dm2.games, 0) AS game_losses,
            d2.name AS opponent_deck_name,
            {person_query} AS opponent
        FROM `match` AS m
        INNER JOIN deck_match AS dm1 ON m.id = dm1.match_id AND dm1.deck_id = %s
        LEFT JOIN deck_match AS dm2 ON m.id = dm2.match_id AND dm2.deck_id <> %s
        INNER JOIN deck AS d1 ON dm1.deck_id = d1.id
        LEFT JOIN deck AS d2 ON dm2.deck_id = d2.id
        LEFT JOIN person AS p ON p.id = d2.person_id
        ORDER BY round
    """.format(person_query=query.person_query())
    matches = [Container(m) for m in db().execute(sql, [d.id, d.id])]
    if should_load_decks:
        opponents = [m.opponent_deck_id for m in matches if m.opponent_deck_id is not None]
        if len(opponents) > 0:
            decks = load_decks('d.id IN ({ids})'.format(ids=', '.join([sqlescape(str(deck_id)) for deck_id in opponents])))
        else:
            decks = []
        decks_by_id = {d.id: d for d in decks}
    for m in matches:
        m.date = dtutil.ts2dt(m.date)
        if should_load_decks and m.opponent_deck_id is not None:
            m.opponent_deck = decks_by_id[m.opponent_deck_id]
        elif should_load_decks:
            m.opponent_deck = None
    return matches

def load_decks_by_cards(names):
    sql = """
        d.id IN (
            SELECT deck_id
            FROM deck_card
            WHERE card IN ({names})
            GROUP BY deck_id
            HAVING COUNT(DISTINCT card) = {n})
        """.format(n=len(names), names=', '.join(map(sqlescape, names)))
    return load_decks(sql)

def load_cards(decks):
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
def load_opponent_stats(decks):
    if len(decks) == 0:
        return
    decks_by_id = {d.id: d for d in decks}
    sql = """
        SELECT d.id,
            SUM(opp.wins) AS opp_wins, SUM(opp.losses) AS opp_losses, ROUND(SUM(opp.wins) / (SUM(opp.wins) + SUM(opp.losses)), 2) * 100 AS omw,
            IFNULL(MIN(CASE WHEN m.elimination > 0 THEN m.elimination END), 0) AS stage_reached, GROUP_CONCAT(m.elimination) AS elim
        FROM deck AS d
        LEFT JOIN deck AS opp ON opp.id IN (SELECT deck_id FROM deck_match WHERE deck_id <> d.id AND match_id IN (SELECT match_id FROM deck_match WHERE deck_id = d.id))
        LEFT JOIN deck_match AS dm ON d.id = dm.deck_id
        LEFT JOIN `match` AS m ON m.id = dm.match_id
        WHERE d.id IN ({deck_ids})
        GROUP BY d.id
    """.format(deck_ids=', '.join(map(sqlescape, map(str, decks_by_id.keys()))))
    for row in db().execute(sql):
        decks_by_id[row['id']].opp_wins = row['opp_wins']
        decks_by_id[row['id']].opp_losses = row['opp_losses']
        decks_by_id[row['id']].omw = row['omw']
        decks_by_id[row['id']].stage_reached = row['stage_reached']
        decks_by_id[row['id']].elim = row['elim'] # This property is never used? and is always a bunch of zeroes?

# pylint: disable=too-many-instance-attributes
class Deck(Container):
    def __init__(self, params):
        super().__init__()
        for k in params.keys():
            self[k] = params[k]

    def all_cards(self):
        cards = []
        for entry in self.maindeck + self.sideboard:
            cards += [entry['card']] * entry['n']
        return cards

    def __str__(self):
        s = ''
        for entry in self.maindeck:
            s += '{n} {name}\n'.format(n=entry['n'], name=entry['name'])
        s += '\n'
        for entry in self.sideboard:
            s += '{n} {name}\n'.format(n=entry['n'], name=entry['name'])
        return s
