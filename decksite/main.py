import os

from flask import Flask, request, send_from_directory

from decksite.data import card as cs, competition as comp, deck, person as ps
from decksite.views import About, AddForm, Card, Cards, Competition, Competitions, Deck, Home, People, Person

from magic import legality

APP = Flask(__name__)

@APP.route('/')
def home():
    view = Home(deck.latest_decks())
    return view.page()

@APP.route('/decks/<deck_id>')
def decks(deck_id):
    view = Deck(deck.load_deck(deck_id))
    return view.page()

@APP.route('/people')
def people():
    view = People(ps.load_people())
    return view.page()

@APP.route('/people/<person_id>')
def person(person_id):
    view = Person(ps.load_person(person_id))
    return view.page()

@APP.route('/cards')
def cards():
    view = Cards(cs.played_cards())
    return view.page()

@APP.route('/cards/<name>')
def card(name):
    view = Card(cs.load_card(name))
    return view.page()

@APP.route('/competitions')
def competitions():
    view = Competitions(comp.load_competitions())
    return view.page()

@APP.route('/competitons/<competition_id>')
def competition(competition_id):
    view = Competition(comp.load_competition(competition_id))
    return view.page()

@APP.route('/add')
def add_form():
    view = AddForm()
    return view.page()

@APP.route('/add', methods=['POST'])
def add_deck():
    decks.add_deck(request.form)
    return add_form()

@APP.route('/about')
def about():
    view = About()
    return view.page()

@APP.route('/querytappedout')
def deckcycle_tappedout():
    from decksite.scrapers import tappedout
    if not tappedout.is_authorised():
        tappedout.login()
    tappedout.scrape()
    return home()

@APP.route('/favicon<rest>')
def favicon(rest):
    return send_from_directory(os.path.join(APP.root_path, 'static/images/favicon'), 'favicon{rest}'.format(rest=rest))

def init():
    legality.init()
    APP.run(host='0.0.0.0', debug=True)
