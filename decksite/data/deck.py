from decksite.database import get_db

def latest_decks():
    sql = """
        SELECT d.id, IFNULL(IFNULL(p.name, p.mtgo_username), p.tappedout_username) AS person, d.name
        FROM deck AS d
        INNER JOIN person AS p ON d.person_id = p.id
        ORDER BY updated_date DESC
        LIMIT 20
    """
    return get_db().execute(sql)

def load_deck(deck_id):
    sql = """
        SELECT d.id, IFNULL(IFNULL(p.name, p.mtgo_username), p.tappedout_username) AS person, d.name,
            d.created_date, d.updated_date
        FROM deck AS d
        INNER JOIN person AS p ON d.person_id = p.id
        WHERE d.id = ?
    """
    return get_db().execute(sql, [deck_id])[0]

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
        raise Exception(params)
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

def insert_deck_card(deck_id, card, n, in_sideboard):
    sql = 'INSERT INTO deck_card (deck_id, card, n, sideboard) VALUES (?, ?, ?, ?)'
    return get_db().execute(sql, [deck_id, card, n, in_sideboard])

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
        raise Exception('Unkown source: `{source}`'.format(source=source))
    return source_id

class Deck(dict):
    def __init__(self, params):
        super().__init__()
        for k in params.keys():
            self[k] = params[k]
