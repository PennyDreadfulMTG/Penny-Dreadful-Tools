from flask import Flask, g, request

from decksite import tappedout
from decksite.data import deck
from decksite.views import AddForm, Deck, Home

APP = Flask(__name__)

@APP.teardown_appcontext
def close_db(error):
    #pylint: disable=unused-argument
    """Closes the database again at the end of the request."""
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()

@APP.route('/')
def home():
    # Uncomment this to get data for testing. It's slow, though, so probably turn it off against after that.
    if not tappedout.is_authorised():
        tappedout.login()
    tappedout.fetch_decks('penny-dreadful')
    view = Home(deck.latest_decks())
    return view.page()

@APP.route("/decks/<deck_id>")
def decks(deck_id):
    view = Deck(deck.load_deck(deck_id))
    return view.page()

@APP.route('/add')
def add_form():
    view = AddForm()
    return view.page()

@APP.route('/add', methods=['POST'])
def add_deck():
    decks.add_deck(request.form)
    return add_form()

def init():
    APP.run(debug=True)
