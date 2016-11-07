import os
import re

from flask import Flask, make_response, redirect, request, send_from_directory, url_for
from werkzeug import exceptions

from shared.pd_exception import DoesNotExistException

from decksite import league as lg
from decksite.data import card as cs, competition as comp, deck, person as ps
from decksite.league import ReportForm, SignUpForm
from decksite.views import About, AddForm, Card, Cards, Competition, Competitions, Deck, Home, InternalServerError, NotFound, People, Person, Report, Resources, SignUp

APP = Flask(__name__)

# Decks

@APP.route('/')
def home():
    view = Home(deck.latest_decks())
    return view.page()

@APP.route('/decks/<deck_id>/')
def decks(deck_id):
    view = Deck(deck.load_deck(deck_id))
    return view.page()

@APP.route('/people/')
def people():
    view = People(ps.load_people())
    return view.page()

@APP.route('/people/<person_id>/')
def person(person_id):
    try:
        p = ps.load_person(person_id)
    except DoesNotExistException:
        p = ps.load_person_by_username(person_id)
    view = Person(p)
    return view.page()

@APP.route('/cards/')
def cards():
    view = Cards(cs.played_cards())
    return view.page()

@APP.route('/cards/<name>/')
def card(name):
    view = Card(cs.load_card(name))
    return view.page()

@APP.route('/competitions/')
def competitions():
    view = Competitions(comp.load_competitions())
    return view.page()

@APP.route('/competitions/<competition_id>/')
def competition(competition_id):
    view = Competition(comp.load_competition(competition_id))
    return view.page()

@APP.route('/add/')
def add_form():
    view = AddForm()
    return view.page()

@APP.route('/add/', methods=['POST'])
def add_deck():
    decks.add_deck(request.form)
    return redirect(url_for('add'))

@APP.route('/about/')
def about():
    view = About()
    return view.page()

@APP.route('/export/<deck_id>/')
def export(deck_id):
    d = deck.load_deck(deck_id)
    safe_name = re.sub('[^0-9a-z-]', '-', d.name, flags=re.IGNORECASE)
    return (str(d), 200, {'Content-type': 'text/plain; charset=utf-8', 'Content-Disposition': 'attachment; filename={name}.txt'.format(name=safe_name)})

@APP.route('/resources/')
def resources():
    view = Resources()
    return view.page()

# League

@APP.route('/signup/')
def signup(form=None):
    if form is None:
        form = SignUpForm(request.form)
    view = SignUp(form)
    return view.page()

@APP.route('/signup/', methods=['POST'])
def add_signup():
    form = SignUpForm(request.form)
    if form.validate():
        deck_id = lg.signup(form)
        response = make_response(redirect(url_for('decks', deck_id=deck_id)))
        print(deck_id)
        response.set_cookie('deck_id', str(deck_id))
        return response
    else:
        return signup(form)

@APP.route('/report/')
def report(form=None):
    if form is None:
        form = ReportForm(request.form, request.cookies.get('deck_id', ''))
    view = Report(form)
    return view.page()

@APP.route('/report/', methods=['POST'])
def add_report():
    form = ReportForm(request.form)
    if form.validate():
        lg.report(form)
        response = make_response(redirect(url_for('decks', deck_id=form.entry)))
        response.set_cookie('deck_id', form.entry)
        return response
    else:
        return report(form)

# Admin

@APP.route('/querytappedout/')
def deckcycle_tappedout():
    from decksite.scrapers import tappedout
    if not tappedout.is_authorised():
        tappedout.login()
    tappedout.scrape()
    return home()

# Infra

@APP.route('/favicon<rest>/')
def favicon(rest):
    return send_from_directory(os.path.join(APP.root_path, 'static/images/favicon'), 'favicon{rest}'.format(rest=rest))

@APP.errorhandler(DoesNotExistException)
@APP.errorhandler(exceptions.NotFound)
def not_found(e):
    view = NotFound(e)
    return view.page(), 404

@APP.errorhandler(exceptions.InternalServerError)
def internal_server_error(e):
    view = InternalServerError(e)
    return view.page(), 500

def init():
    APP.run(host='0.0.0.0', debug=True)
