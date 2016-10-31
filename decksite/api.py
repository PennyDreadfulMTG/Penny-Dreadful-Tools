import json

from shared import configuration

from decksite.main import APP
from decksite.scrapers import tappedout

def auth():
    if not tappedout.is_authorised():
        tappedout.login(configuration.get('to_username'), configuration.get('to_password'))

@APP.route("/api/tappedout/")
def tappedout_recent():
    auth()
    return json.dumps(tappedout.fetch_decks())

@APP.route("/api/deck/<slug>")
def deck_api(slug):
    deck = slug
    return json.dumps(deck)
