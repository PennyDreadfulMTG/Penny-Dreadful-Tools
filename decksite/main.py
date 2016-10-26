from flask import Flask, g, request

from magic import configuration

from decksite import tappedout, template
from decksite.views import AddForm, Home

APP = Flask(__name__)

@APP.teardown_appcontext
def close_db(error):
    #pylint: disable=unused-argument
    """Closes the database again at the end of the request."""
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()

@APP.route('/')
def home():
    if not tappedout.is_authorised():
        tappedout.login(configuration.get('to_username'), configuration.get('to_password'))
    view = Home(tappedout.fetch_decks('penny-dreadful'))
    return view.page()

@APP.route("/decks/<slug>")
def decks(slug):
    deck = tappedout.fetch_deck(slug)
    return render_template("deck.html", deck=deck)

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
