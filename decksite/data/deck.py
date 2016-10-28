from munch import Munch
from flask import url_for

from magic import mana, oracle
from pd_exception import InvalidDataException

from decksite.database import escape, get_db

def latest_decks():
    return load_decks(limit='LIMIT 100')

def load_deck(deck_id):
    return load_decks('d.id = {deck_id}'.format(deck_id=escape(deck_id)))[0]

def load_decks(where='1 = 1', order_by='updated_date DESC', limit=''):
    sql = """
        SELECT d.id, IFNULL(IFNULL(p.name, p.mtgo_username), p.tappedout_username) AS person, d.name,
            d.created_date, d.updated_date
        FROM deck AS d
        INNER JOIN person AS p ON d.person_id = p.id
        WHERE {where}
        ORDER BY {order_by}
        {limit}
    """.format(where=where, order_by=order_by, limit=limit)
    decks = [Deck(d) for d in get_db().execute(sql)]
    load_cards(decks)
    for d in decks:
        set_colors(d)
        set_legality(d)
    return decks

def load_cards(decks):
    sql = """
        SELECT deck_id, card, n, sideboard FROM deck_card WHERE deck_id IN (?)
    """
    deck_ids = ', '.join(str(deck.id) for deck in decks)
    rs = get_db().execute(sql, [deck_ids])
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
    required = set()
    for card in [c['card'] for c in d.maindeck + d.sideboard]:
        # BUG: We're ignoring split cards here because they are hard.
        if card.mana_cost and '//' not in card.name:
            colors = mana.colors(mana.parse(card.mana_cost))
            required.update(colors['required'])
    d.colors = required

def set_legality(d):
    d.pd_legal = oracle.legal([c['card'] for c in d.cards()])

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
# Optionally: resource_uri, featured_card, score, thumbnail_url, small_thumbnail_url
#
# url + identifier must be unique for each decklist.
def add_deck(params):
    if not params.get('mtgo_username') and not params.get('tappedout_username'):
        raise InvalidDataException('Did not find a username in {params}'.format(params=params))
    person_id = get_or_insert_person_id(params.get('mtgo_username'), params.get('tappedout_username'))
    deck_id = get_deck_id(params['url'], params['identifier'])
    if deck_id:
        return deck_id
    source_id = get_source_id(params['source'])
    sql = "INSERT INTO deck (person_id, source_id, url, identifier, name, created_date, updated_date, resource_uri, featured_card, score, thumbnail_url, small_thumbnail_url) VALUES (?, ?, ?, ?, ?, datetime('now', 'unixepoch'), datetime('now', 'unixepoch'), ?, ?, ?, ?, ?)"
    values = [person_id, source_id, params['url'], params['identifier'], params['name'], params.get('resource_uri'), params.get('featured_card'), params.get('score'), params.get('thumbnail_url'), params.get('small_thumbnail_url')]
    deck_id = get_db().insert(sql, values)
    for name, n in params['cards']['maindeck'].items():
        insert_deck_card(deck_id, name, n, False)
    for name, n in params['cards']['sideboard'].items():
        insert_deck_card(deck_id, name, n, True)
    return deck_id

def get_deck_id(url, identifier):
    sql = 'SELECT id FROM deck WHERE url = ? AND identifier = ?'
    return get_db().value(sql, [url, identifier])

def insert_deck_card(deck_id, name, n, in_sideboard):
    try:
        cards = oracle.cards_from_query(name, 20)
        if len(cards) > 1:
            raise InvalidDataException('Found more than one card looking for {name}'.format(name=name))
        card = cards[0]
    except IndexError:
        raise InvalidDataException('Did not find any cards looking for {name}'.format(name=name))
    sql = 'INSERT INTO deck_card (deck_id, card, n, sideboard) VALUES (?, ?, ?, ?)'
    return get_db().execute(sql, [deck_id, card.name, n, in_sideboard])

def get_or_insert_person_id(mtgo_username, tappedout_username):
    sql = 'SELECT id FROM person WHERE mtgo_username = ? OR tappedout_username = ?'
    person_id = get_db().value(sql, [mtgo_username, tappedout_username])
    if person_id:
        return person_id
    sql = 'INSERT INTO person (mtgo_username, tappedout_username) VALUES (?, ?)'
    return get_db().insert(sql, [mtgo_username, tappedout_username])

def get_source_id(source):
    sql = 'SELECT id FROM source WHERE name = ?'
    source_id = get_db().value(sql, [source])
    if not source_id:
        raise InvalidDataException('Unkown source: `{source}`'.format(source=source))
    return source_id

class Deck(Munch):
    def __init__(self, params):
        super().__init__()
        for k in params.keys():
            self[k] = params[k]
        self.url = url_for('decks', deck_id=self.id)

    def cards(self):
        return self.maindeck + self.sideboard
