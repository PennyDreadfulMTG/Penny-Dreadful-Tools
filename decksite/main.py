from flask import Flask, g, render_template

from decksite import tappedout
from magic import configuration

APP = Flask(__name__)

@APP.teardown_appcontext
def close_db(error):
    #pylint: disable=unused-argument
    """Closes the database again at the end of the request."""
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()

@APP.route('/')
def list_decks():
    if not tappedout.is_authorised():
        tappedout.login(configuration.get('to_username'), configuration.get('to_password'))
    return render_template("raw.html", decks=tappedout.fetch_decks('penny-dreadful'))

@APP.route("/deck/<slug>")
def display_deck(slug):
    deck = tappedout.fetch_deck(slug)
    return render_template("deck.html", deck=deck)

def init():
    APP.run(debug=True)
