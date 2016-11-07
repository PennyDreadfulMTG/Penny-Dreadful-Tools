from munch import Munch

from magic import mana, oracle, legality
from shared import dtutil
from shared.database import sqlescape
from shared.pd_exception import InvalidDataException

from decksite.data import guarantee, query
from decksite.database import db

def latest_decks():
    return load_decks(limit='LIMIT 1000')

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
            d.created_date AS `date`,
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
    return decks

def load_cards(decks):
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

    if "Penny Dreadful" in d.legal_formats:
        d.legal_icons += '<i class="ss ss-kld ss-rare ss-grad">S2</i>'
    # We need to make this better. Something to be done before AER is released.
    for fmt in d.legal_formats:
        if fmt.startswith("Penny Dreadful "):
            d.legal_icons += '<i class="ss ss-{set} ss-common ss-grad">S1</i>'.format(set=fmt[15:].lower())
    # if "Modern" in d.legal_formats:
    #     d.legal_icons += '<i class="ss ss-8ed ss-uncommon ss-grad icon-modern">MDN</i>'

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
        return deck_id
    archetype_id = get_archetype_id(params.get('archetype'))
    for result in ['wins', 'losses', 'draws']:
        if params.get('competition_id') and not params.get(result):
            params[result] = 0
    sql = 'BEGIN TRANSACTION'
    db().execute(sql)
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
         IFNULL(?, strftime('%s', 'now')),  strftime('%s', 'now'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
    )"""
    values = [
        params.get('created_date'),
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
    for name, n in params['cards']['maindeck'].items():
        insert_deck_card(deck_id, name, n, False)
    for name, n in params['cards']['sideboard'].items():
        insert_deck_card(deck_id, name, n, True)
    sql = 'COMMIT'
    db().execute(sql)
    return deck_id

def get_deck_id(source_name, identifier):
    source_id = get_source_id(source_name)
    sql = 'SELECT id FROM deck WHERE source_id = ? AND identifier = ?'
    return db().value(sql, [source_id, identifier])

def insert_deck_card(deck_id, name, n, in_sideboard):
    card = oracle.valid_name(name)
    sql = 'INSERT INTO deck_card (deck_id, card, n, sideboard) VALUES (?, ?, ?, ?)'
    return db().execute(sql, [deck_id, card, n, in_sideboard])

def get_or_insert_person_id(mtgo_username, tappedout_username):
    sql = 'SELECT id FROM person WHERE mtgo_username = ? OR tappedout_username = ?'
    person_id = db().value(sql, [mtgo_username, tappedout_username])
    if person_id:
        return person_id
    sql = 'INSERT INTO person (mtgo_username, tappedout_username) VALUES (?, ?)'
    return db().insert(sql, [mtgo_username, tappedout_username])

def get_source_id(source):
    sql = 'SELECT id FROM source WHERE name = ?'
    source_id = db().value(sql, [source])
    if not source_id:
        raise InvalidDataException('Unknown source: `{source}`'.format(source=source))
    return source_id

def get_archetype_id(archetype):
    sql = 'SELECT id FROM archetype WHERE name = ?'
    return db().value(sql, [archetype])

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
