import re

from magic import configuration, fetcher, fetcher_internal

from decksite import translation
from decksite.data import deck, Deck
from decksite.database import get_db

def fetch_decks(hub: str):
    deckcycle = fetcher.fetch_json("http://tappedout.net/api/deck/latest/{0}/".format(hub))
    return [Deck(merge_deck(d)) for d in deckcycle]

def fetch_deck(slug: str):
    deckinfo = fetcher.fetch_json("http://tappedout.net/api/collection/collection:deck/{0}/".format(slug))
    deck_id = store_deck(deckinfo)
    return deck.load_deck(deck_id)

def merge_deck(blob):
    deck_id = store_deck(translation.translate(translation.TAPPEDOUT, blob))
    d = deck.load_deck(deck_id)
    # this will never fire
    # if d.updated_date is None and is_authorised():
    #     deck_id = fetch_deck(blog.get('slug'))
    #     d = load_deck(deck_id)
    return d

def store_deck(blob):
    keys = ['slug', 'name', 'tappedout_username', 'url', 'resource_uri', 'featured_card', 'date_updated', 'score', 'thumbnail_url', 'small_thumbnail_url']
    d = {key: blob.get(key) for key in keys if key in blob.keys()}
    decklist = fetcher.fetch('{base_url}?fmt=txt'.format(base_url=blob['url']))
    d['cards'] = parse_decklist(decklist)
    d['source'] = 'Tapped Out'
    d['identifier'] = d['url']
    return deck.add_deck(d)

def parse_decklist(s):
    d = {'maindeck': {}, 'sideboard': {}}
    part = 'maindeck'
    for line in s.split('\n'):
        if line.startswith('Sideboard'):
            part = 'sideboard'
        elif line == '':
            pass
        else:
            n, card = line.split('\t')
            d[part][card] = n
    return d

def insert_inventory(slug, inventory):
    assert inventory is not None
    db = get_db()
    deck_id = db.value("SELECT id from decks WHERE slug = ?", [slug])
    rs = db.execute("SELECT * from decklists WHERE deckid = ?", [deck_id])
    if len(rs) > 0:
        # Make this better
        db.execute("DELETE from decklists WHERE deckid = ?", [deck_id])
    for name, board in inventory:
        db.execute("INSERT INTO decklists (deckid, name, count, board) VALUES (?,?,?,?)", [deck_id, name, board['qty'], board['b']])

def is_authorised():
    return fetcher_internal.SESSION.cookies.get('tapped') is not None

def get_auth():
    cookie = fetcher_internal.SESSION.cookies.get('tapped')
    token = configuration.get("tapped_API_key")
    return fetcher.fetch("http://tappedout.net/api/v1/cookie/{0}/?access_token={1}".format(cookie, token))

def login(user=None, password=None):
    if user is None:
        user = configuration.get('to_username')
    if password is None:
        password = configuration.get('to_password')
    if user == '' or password == '':
        print('No TappedOut credentials provided')
        return
    url = "http://tappedout.net/accounts/login/"
    session = fetcher_internal.SESSION
    response = session.get(url)

    match = re.search(r"<input type='hidden' name='csrfmiddlewaretoken' value='(\w+)' />", response.text)
    if match is None:
        # Already logged in?
        return
    csrf = match.group(1)

    data = {
        'csrfmiddlewaretoken': csrf,
        'next': '/',
        'username': user,
        'password': password,
    }
    response = session.post(url, data=data)
