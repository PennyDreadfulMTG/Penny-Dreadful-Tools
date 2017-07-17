import hashlib
import json
import time

from magic import mana, oracle, legality
from shared import dtutil
from shared.container import Container
from shared.database import sqlescape
from shared.pd_exception import InvalidDataException

from decksite.data import guarantee, query
from decksite.database import db

def latest_decks():
    return load_decks(limit='LIMIT 500')

def load_deck(deck_id):
    return guarantee.exactly_one(load_decks('d.id = {deck_id}'.format(deck_id=sqlescape(deck_id))))

# pylint: disable=attribute-defined-outside-init
def load_decks(where='1 = 1', order_by=None, limit=''):
    if order_by is None:
        order_by = 'd.created_date DESC, IFNULL(d.finish, 9999999999)'
    sql = """
        SELECT d.id, d.name, d.created_date, d.updated_date, d.wins, d.losses, d.draws, d.finish, d.archetype_id, d.url AS source_url,
            d.competition_id, c.name AS competition_name, c.end_date AS competition_end_date, ct.name AS competition_type_name, d.identifier,
            {person_query} AS person, p.id AS person_id,
            d.created_date AS `date`, d.decklist_hash, d.retired,
            s.name AS source_name, IFNULL(a.name, '') AS archetype_name,
            SUM(opp.wins) AS opp_wins, SUM(opp.losses) AS opp_losses, ROUND(SUM(opp.wins) / (SUM(opp.wins) + SUM(opp.losses)), 2) * 100 AS omw,
            GROUP_CONCAT(DISTINCT CONCAT(dc.card, '|', dc.n, '|', dc.sideboard) SEPARATOR '█') AS cards,
            cache.colors, cache.colored_symbols, cache.legal_formats
        FROM deck AS d
        INNER JOIN person AS p ON d.person_id = p.id
        LEFT JOIN competition AS c ON d.competition_id = c.id
        INNER JOIN source AS s ON d.source_id = s.id
        LEFT JOIN archetype AS a ON d.archetype_id = a.id
        LEFT JOIN deck AS opp ON opp.id IN (SELECT deck_id FROM deck_match WHERE deck_id <> d.id AND match_id IN (SELECT match_id FROM deck_match WHERE deck_id = d.id))
        LEFT JOIN competition_type AS ct ON ct.id = c.competition_type_id
        LEFT JOIN deck_card AS dc ON d.id = dc.deck_id
        LEFT JOIN deck_cache AS cache ON d.id = cache.deck_id
        WHERE {where}
        GROUP BY d.id
        ORDER BY {order_by}
        {limit}
    """.format(person_query=query.person_query(), where=where, order_by=order_by, limit=limit)
    db().execute('SET group_concat_max_len=100000')
    rows = db().execute(sql)
    cards = oracle.cards_by_name()
    decks = []
    for row in rows:
        d = Deck(row)
        d.maindeck = []
        d.sideboard = []
        cards_s = (row['cards'] or '')
        for entry in filter(None, cards_s.split('█')):
            name, n, is_sideboard = entry.split('|')
            location = 'sideboard' if bool(int(is_sideboard)) else 'maindeck'
            d[location].append({'n': int(n), 'name': name, 'card': cards[name]})
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
    return decks

# We ignore 'also' here which means if you are playing a deck where there are no other G or W cards than Kitchen Finks
# we will claim your deck is neither W nor G which is not true. But this should cover most cases.
# We also ignore split cards so if you are genuinely using a color in a split card but have no other cards of that color
# we won't claim it as one of the deck's colors.
def set_colors(d):
    deck_colors = set()
    deck_colored_symbols = []
    for card in [c['card'] for c in d.maindeck + d.sideboard]:
        for cost in card.get('mana_cost') or ():
            if card.layout == 'split':
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
# Plus one of: mtgo_username OR tappedout_username
# Optionally: created_date (unix timestamp, defaults to now), resource_uri, featured_card, score, thumbnail_url, small_thumbnail_url, wins, losses, draws, finish
#
# source + identifier must be unique for each decklist.
def add_deck(params):
    if not params.get('mtgo_username') and not params.get('tappedout_username'):
        raise InvalidDataException('Did not find a username in {params}'.format(params=params))
    person_id = get_or_insert_person_id(params.get('mtgo_username'), params.get('tappedout_username'))
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
    db().begin()
    db().execute('DELETE FROM deck_cache WHERE deck_id = ?', [d.id])
    db().execute('INSERT INTO deck_cache (deck_id, colors, colored_symbols, legal_formats) VALUES (?, ?, ?, ?)', [d.id, colors_s, colored_symbols_s, legal_formats_s])
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

def get_or_insert_person_id(mtgo_username, tappedout_username):
    sql = 'SELECT id FROM person WHERE LOWER(mtgo_username) = LOWER(%s) OR LOWER(tappedout_username) = LOWER(%s)'
    person_id = db().value(sql, [mtgo_username, tappedout_username])
    if person_id:
        return person_id
    sql = 'INSERT INTO person (mtgo_username, tappedout_username) VALUES (%s, %s)'
    return db().insert(sql, [mtgo_username, tappedout_username])

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
    return float(score) / float(len(b.maindeck))

def insert_match(dt, left_id, left_games, right_id, right_games, round_num=None, elimination=False):
    match_id = db().insert("INSERT INTO `match` (`date`, `round`, elimination) VALUES (%s, %s, %s)", [dtutil.dt2ts(dt), round_num, elimination])
    sql = 'INSERT INTO deck_match (deck_id, match_id, games) VALUES (%s, %s, %s)'
    db().execute(sql, [left_id, match_id, left_games])
    if right_id is not None: # Don't insert matches for the bye.
        db().execute(sql, [right_id, match_id, right_games])
    return match_id

def get_matches(d, load_decks=False):
    sql = """
        SELECT
            m.`date`, m.id, m.round, m.elimination,
            dm1.games AS game_wins,
            dm2.deck_id AS opponent_deck_id, dm2.games AS game_losses,
            d2.name AS opponent_deck_name,
            p.mtgo_username AS opponent
        FROM `match` AS m
        INNER JOIN deck_match AS dm1 ON m.id = dm1.match_id AND dm1.deck_id = %s
        INNER JOIN deck_match AS dm2 ON m.id = dm2.match_id AND dm2.deck_id <> %s
        INNER JOIN deck AS d1 ON dm1.deck_id = d1.id
        INNER JOIN deck AS d2 ON dm2.deck_id = d2.id
        INNER JOIN person AS p ON p.id = d2.person_id
        ORDER BY round
    """
    matches = [Container(m) for m in db().execute(sql, [d.id, d.id])]
    if load_decks and len(matches) > 0:
        decks = deck.load_decks('d.id IN ({ids})'.format(ids=', '.join([sqlescape(str(m.opponent_deck_id)) for m in matches])))
        decks_by_id = {d.id: d for d in decks}
    for m in matches:
        m.date = dtutil.ts2dt(m.date)
        if load_decks:
            m.opponent_deck = decks_by_id[m.opponent_deck_id]
    return matches

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
