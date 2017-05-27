import hashlib
import time

from munch import Munch

from magic import mana, oracle, legality, rotation
from shared import dtutil
from shared.database import sqlescape
from shared.pd_exception import InvalidDataException

from decksite.data import guarantee, query
from decksite.database import db

def latest_decks():
    return load_decks(limit='LIMIT 500')

def load_deck(deck_id):
    return guarantee.exactly_one(load_decks('d.id = {deck_id}'.format(deck_id=sqlescape(deck_id))))

def load_decks(where='1 = 1', order_by=None, limit=''):
    if order_by is None:
        order_by = 'd.created_date DESC, IFNULL(finish, 9999999999)'
    sql = """
        SELECT d.id, d.name, d.created_date, d.updated_date, d.wins, d.losses, d.draws, d.finish, d.url AS source_url,
            (SELECT COUNT(id) FROM deck WHERE competition_id IS NOT NULL AND competition_id = d.competition_id) AS players,
            d.competition_id, c.name AS competition_name, c.end_date AS competition_end_date,
            {person_query} AS person, p.id AS person_id,
            d.created_date AS `date`, d.decklist_hash, d.retired,
            s.name AS source_name
        FROM deck AS d
        INNER JOIN person AS p ON d.person_id = p.id
        LEFT JOIN competition AS c ON d.competition_id = c.id
        INNER JOIN source AS s ON d.source_id = s.id
        WHERE {where}
        ORDER BY {order_by}
        {limit}
    """.format(person_query=query.person_query(), where=where, order_by=order_by, limit=limit)
    decks = [Deck(d) for d in db().execute(sql)]
    load_cards(decks)
    for d in decks:
        d.created_date = dtutil.ts2dt(d.created_date)
        d.updated_date = dtutil.ts2dt(d.updated_date)
        if d.competition_end_date:
            d.competition_end_date = dtutil.ts2dt(d.competition_end_date)
        d.date = dtutil.ts2dt(d.date)
        set_colors(d)
        set_legality(d)
        set_twins(d)
        d.has_record = d.competition_id is not None or True in [True for x in d.twins if x.competition_id is not None]
        d.can_draw = "Divine Intervention" in [card.name for card in d.all_cards()]
    return decks

def load_cards(decks):
    if decks == []:
        return
    deck_ids = ', '.join(str(sqlescape(deck.id)) for deck in decks)
    sql = """
        SELECT deck_id, card, n, sideboard FROM deck_card WHERE deck_id IN ({deck_ids})
    """.format(deck_ids=deck_ids)
    rs = db().execute(sql)
    names = {row['card'] for row in rs}
    cards = {card.name: card for card in oracle.load_cards(names)}
    ds = {deck.id: deck for deck in decks}
    for d in decks:
        d.maindeck = []
        d.sideboard = []
    for row in rs:
        location = 'sideboard' if row['sideboard'] else 'maindeck'
        ds[row['deck_id']][location].append({'n': row['n'], 'name': row['card'], 'card': cards[row['card']]})
    for d in decks:
        d['maindeck'].sort(key=lambda x: oracle.deck_sort(x['card']))
        d['sideboard'].sort(key=lambda x: oracle.deck_sort(x['card']))

# We ignore 'also' here which means if you are playing a deck where there are no other G or W cards than Kitchen Finks
# we will claim your deck is neither W nor G which is not true. But this should cover most cases.
def set_colors(d):
    deck_colors = set()
    deck_colored_symbols = []
    for card in [c['card'] for c in d.maindeck + d.sideboard]:
        for cost in card.get('mana_cost') or ():
            card_symbols = mana.parse(cost)
            card_colors = mana.colors(card_symbols)
            deck_colors.update(card_colors['required'])
            card_colored_symbols = mana.colored_symbols(card_symbols)
            deck_colored_symbols += card_colored_symbols['required']
    d.colors = mana.order(deck_colors)
    d.colored_symbols = deck_colored_symbols

def set_legality(d):
    d.legal_formats = legality.legal_formats(d)
    d.has_legal_format = len(d.legal_formats) > 0
    d.pd_legal = "Penny Dreadful" in d.legal_formats
    d.legal_icons = ""

    sets = ["EMN", "KLD", "AER", "AKH", "HOU"]

    if "Penny Dreadful" in d.legal_formats:
        icon = rotation.last_rotation_ex()['code'].lower()
        n = sets.index(icon.upper()) + 1
        d.legal_icons += '<i class="ss ss-{code} ss-rare ss-grad">S{n}</i>'.format(code=icon, n=n)

    for fmt in d.legal_formats:
        if fmt.startswith("Penny Dreadful "):
            n = sets.index(fmt[15:].upper()) + 1
            d.legal_icons += '<i class="ss ss-{set} ss-common ss-grad">S{n}</i>'.format(set=fmt[15:].lower(), n=n)
    # if "Modern" in d.legal_formats:
    #     d.legal_icons += '<i class="ss ss-8ed ss-uncommon ss-grad icon-modern">MDN</i>'
    if "Commander" in d.legal_formats: #I think C16 looks the nicest.
        d.legal_icons += '<i class="ss ss-c16 ss-uncommon ss-grad">CMDR</i>'

def set_twins(deck):
    sql = """
        SELECT d.id, d.name, d.created_date, d.updated_date, d.wins, d.losses, d.draws, d.finish, d.url AS source_url,
            (SELECT COUNT(id) FROM deck WHERE competition_id IS NOT NULL AND competition_id = d.competition_id) AS players,
            d.competition_id, c.name AS competition_name, c.end_date AS competition_end_date,
            {person_query} AS person, p.id AS person_id,
            d.created_date AS `date`, d.decklist_hash,
            s.name AS source_name
        FROM deck AS d
        INNER JOIN person AS p ON d.person_id = p.id
        LEFT JOIN competition AS c ON d.competition_id = c.id
        INNER JOIN source AS s ON d.source_id = s.id
        WHERE decklist_hash = "{hash}" AND d.id <> {id}
        """.format(person_query=query.person_query(), hash=deck.decklist_hash, id=deck.id)
    decks = [Deck(d) for d in db().execute(sql)]
    for d in decks:
        d.created_date = dtutil.ts2dt(d.created_date)
        d.updated_date = dtutil.ts2dt(d.updated_date)
        if d.competition_end_date:
            d.competition_end_date = dtutil.ts2dt(d.competition_end_date)
        d.date = dtutil.ts2dt(d.date)
    deck.twins = decks

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
    db().begin()
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
        finish
    ) VALUES (
         IFNULL(%s, UNIX_TIMESTAMP()),  UNIX_TIMESTAMP(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
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
    db().commit()
    add_cards(deck_id, params['cards'])
    return deck_id

def add_cards(deck_id, cards):
    db().begin()
    deckhash = hashlib.sha1(repr(cards).encode('utf-8')).hexdigest()
    db().execute("UPDATE deck SET decklist_hash = %s WHERE id = %s", [deckhash, deck_id])
    db().execute("DELETE FROM deck_card WHERE deck_id = %s", [deck_id])
    for name, n in cards['maindeck'].items():
        insert_deck_card(deck_id, name, n, False)
    for name, n in cards['sideboard'].items():
        insert_deck_card(deck_id, name, n, True)
    db().execute("COMMIT")

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

class Deck(Munch):
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
