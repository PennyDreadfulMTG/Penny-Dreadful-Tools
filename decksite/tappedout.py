import re

from magic import configuration, fetcher, fetcher_internal

from decksite import translation
from decksite.data import Deck
from decksite.database import escape, get_db

def fetch_decks(hub: str):
    deckcycle = fetcher.fetch_json("http://tappedout.net/api/deck/latest/{0}/".format(hub))
    return [Deck(mergedeck(d)) for d in deckcycle]

def fetch_deck(slug: str):
    deckinfo = fetcher.fetch_json("http://tappedout.net/api/collection/collection:deck/{0}/".format(slug))
    store_deck(deckinfo)
    return Deck(get_db().execute("SELECT * FROM decks WHERE slug == ?", [slug])[0])

def mergedeck(blob):
    slug = blob.get('slug')
    store_deck(translation.translate(translation.TAPPED_OUT, blob))
    rs = get_db().execute("SELECT * FROM decks WHERE slug == ?", [slug])[0]
    date_updated = rs['date_updated']
    if date_updated is None and is_authorised():
        fetch_deck(rs['slug'])
        rs = get_db().execute("SELECT * FROM decks WHERE slug == ?", [slug])[0]
    return rs

def store_deck(blob):
    keylist = ["slug", "name", "person", "user_display", "url", "resource_uri", "featured_card", "date_updated", "score", "thumbnail_url", "small_thumbnail_url"]
    keylist = [key for key in keylist if key in blob.keys()]
    keys = ', '.join(key for key in keylist)
    values = ', '.join(str(escape(blob.get(key))) if blob.get(key) is not None else "NULL" for key in keylist)
    get_db().execute("INSERT OR IGNORE INTO decks (" + keys + ") VALUES (" + values + ")")

    updates = ', '.join('{name} = {value}'.format(name=name, value=escape(blob.get(name))) for name in keylist)
    get_db().execute("UPDATE decks SET " + updates + " WHERE slug = ?", [blob.get('slug')])
    if blob.get("inventory") is not None:
        insert_inventory(blob['slug'], blob['inventory'])

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

def login(user, password):
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
    print(session.cookies)
    print(response)
