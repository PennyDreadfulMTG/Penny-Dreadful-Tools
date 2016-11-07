import re

from shared import configuration
from magic import fetcher, fetcher_internal

from decksite import translation
from decksite.data import deck
from decksite.scrapers import decklist

def scrape():
    login()
    print('Logged in to TappedOut: {is_authorised}'.format(is_authorised=is_authorised()))
    raw_decks = fetch_decks()
    for raw_deck in raw_decks:
        if is_authorised():
            raw_deck.update(fetch_deck_details(raw_deck))
        raw_deck = set_values(raw_deck)
        deck.add_deck(raw_deck)

def fetch_decks():
    return fetcher_internal.fetch_json('https://tappedout.net/api/deck/latest/penny-dreadful/')

def fetch_deck_details(raw_deck):
    return fetcher_internal.fetch_json("https://tappedout.net/api/collection/collection:deck/{slug}/".format(slug=raw_deck['slug']))

def set_values(raw_deck):
    raw_deck = translation.translate(translation.TAPPEDOUT, raw_deck)
    if 'inventory' in raw_deck:
        raw_deck['cards'] = parse_inventory(raw_deck['inventory'])
    else:
        raw_decklist = fetcher_internal.fetch('{base_url}?fmt=txt'.format(base_url=raw_deck['url']))
        raw_deck['cards'] = decklist.parse(raw_decklist)
    raw_deck['source'] = 'Tapped Out'
    raw_deck['identifier'] = raw_deck['url']
    return raw_deck

def parse_inventory(inventory):
    d = {'maindeck': {}, 'sideboard': {}}
    for name, board in inventory:
        # Decklists can contain editions. eg: Island (INV)
        # We can't handle these right now.
        removeset = re.match(r'([^\(]+)(\(\w\w\w\))?', name)
        if removeset is not None:
            name = removeset.group(1)
        # Same with comments
        removecomments = re.match(r'(.*?)#', name)
        if removecomments is not None:
            name = removecomments.group(1)
        if board['b'] == 'main':
            d['maindeck'][name] = board['qty']
        elif  board['b'] == 'side':
            d['sideboard'][name] = board['qty']
    return d

def is_authorised():
    return fetcher_internal.SESSION.cookies.get('tapped') is not None

def get_auth():
    cookie = fetcher_internal.SESSION.cookies.get('tapped')
    token = configuration.get("tapped_API_key")
    return fetcher_internal.fetch("https://tappedout.net/api/v1/cookie/{0}/?access_token={1}".format(cookie, token))

def login(user=None, password=None):
    if user is None:
        user = configuration.get('to_username')
    if password is None:
        password = configuration.get('to_password')
    if user == '' or password == '':
        print('No TappedOut credentials provided')
        return
    url = "https://tappedout.net/accounts/login/"
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
    headers = {
        'referer': url,
    }
    print("Logging in to TappedOut as {0}".format(user))
    response = session.post(url, data=data, headers=headers)
    if response.status_code == 403:
        print("Failed to log in")
