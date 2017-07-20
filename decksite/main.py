import os
import traceback

from flask import make_response, redirect, request, send_file, send_from_directory, url_for
from werkzeug import exceptions

from magic import oracle
from shared.pd_exception import DoesNotExistException, InvalidArgumentException, InvalidDataException

from decksite import deck_name, league as lg
from decksite import APP
from decksite.cache import cached
from decksite.data import archetype as archs, card as cs, competition as comp, deck, person as ps
from decksite.charts import chart
from decksite.league import ReportForm, SignUpForm
from decksite.views import About, AddForm, Archetype, Archetypes, Card, Cards, Competition, Competitions, Deck, EditArchetypes, Home, InternalServerError, LeagueInfo, NotFound, People, Person, Report, Resources, Rotation, Season, SignUp, Tournaments, Bugs

# Decks

@APP.route('/')
@cached()
def home():
    view = Home(deck.latest_decks())
    return view.page()

@APP.route('/decks/<deck_id>/')
@cached()
def decks(deck_id):
    view = Deck(deck.load_deck(deck_id))
    return view.page()

@APP.route('/season/')
@APP.route('/season/<season_id>')
@cached()
def season(season_id=None):
    view = Season(deck.load_season(season_id))
    return view.page()

@APP.route('/people/')
@cached()
def people():
    view = People(ps.load_people())
    return view.page()

@APP.route('/people/<person_id>/')
@cached()
def person(person_id):
    try:
        p = ps.load_person(person_id)
    except DoesNotExistException:
        p = ps.load_person_by_username(person_id)
    view = Person(p)
    return view.page()

@APP.route('/cards/')
@cached()
def cards():
    view = Cards(cs.played_cards())
    return view.page()

@APP.route('/cards/<path:name>/')
@cached()
def card(name):
    try:
        c = cs.load_card(oracle.valid_name(name.replace('+', ' ')))
        view = Card(c)
        return view.page()
    except InvalidDataException as e:
        raise DoesNotExistException(e)

@APP.route('/competitions/')
@cached()
def competitions():
    view = Competitions(comp.load_competitions())
    return view.page()

@APP.route('/competitions/<competition_id>/')
@cached()
def competition(competition_id):
    view = Competition(comp.load_competition(competition_id))
    return view.page()

@APP.route('/archetypes/')
@cached()
def archetypes():
    view = Archetypes(archs.load_archetypes_deckless())
    return view.page()

@APP.route('/archetypes/<archetype_id>/')
@cached()
def archetype(archetype_id):
    view = Archetype(archs.load_archetype(archetype_id), archs.load_archetypes_deckless_for(archetype_id))
    return view.page()

@APP.route('/tournaments/')
@cached()
def touranments():
    view = Tournaments()
    return view.page()

@APP.route('/add/')
def add_form():
    view = AddForm()
    return view.page()

@APP.route('/add/', methods=['POST'])
@cached()
def add_deck():
    url = request.form['url']
    error = None
    if "tappedout" in url:
        import decksite.scrapers.tappedout
        try:
            deck_id = decksite.scrapers.tappedout.scrape_url(url).id
        except InvalidDataException as e:
            error = e.args[0]
    else:
        error = "Deck host is not supported."
    if error is not None:
        view = AddForm()
        view.error = error
        return view.page(), 409
    return redirect(url_for('decks', deck_id=deck_id))

@APP.route('/about/')
@cached()
def about():
    view = About()
    return view.page()

@APP.route('/rotation/')
@cached()
def rotation():
    view = Rotation()
    return view.page()

@APP.route('/export/<deck_id>/')
def export(deck_id):
    d = deck.load_deck(deck_id)
    safe_name = deck_name.file_name(d)
    return (str(d), 200, {'Content-type': 'text/plain; charset=utf-8', 'Content-Disposition': 'attachment; filename={name}.txt'.format(name=safe_name)})

@APP.route('/resources/')
@cached()
def resources():
    view = Resources()
    return view.page()

@APP.route('/bugs/')
@cached()
def bugs():
    view = Bugs()
    return view.page()

# League

@APP.route('/league/')
def league():
    view = LeagueInfo()
    return view.page()

@APP.route('/signup/')
def signup(form=None):
    if form is None:
        form = SignUpForm(request.form)
    view = SignUp(form)
    return view.page()

@APP.route('/signup/', methods=['POST'])
@cached()
def add_signup():
    form = SignUpForm(request.form)
    if form.validate():
        d = lg.signup(form)
        response = make_response(redirect(url_for('decks', deck_id=d.id)))
        response.set_cookie('deck_id', str(d.id))
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

@APP.route('/admin/archetypes/')
def edit_archetypes(search_results=None):
    if search_results is None:
        search_results = []
    view = EditArchetypes(archs.load_archetypes_deckless(order_by='a.name'), search_results)
    return view.page()

@APP.route('/admin/archetypes/', methods=['POST'])
def post_archetypes():
    search_results = []
    print(request.form)
    if request.form.get('deck_id') is not None:
        archetype_ids = request.form.getlist('archetype_id')
        # Adjust archetype_ids if we're assigning multiple decks to the same archetype.
        if len(archetype_ids) == 1 and len(request.form.getlist('deck_id')) > 1:
            archetype_ids = archetype_ids * len(request.form.getlist('deck_id'))
        for deck_id in request.form.getlist('deck_id'):
            archetype_id = archetype_ids.pop(0)
            if archetype_id:
                archs.assign(deck_id, archetype_id)
    elif request.form.get('q') is not None:
        search_results = deck.load_decks_by_card(request.form.get('q'))
    elif request.form.get('something about assigning is not None'):
        for deck_id in request.form.getlist('deck_id'):
            archs.assign(deck_id, request.form.get('archetype_id'))
    elif request.form.get('parent') is not None:
        archs.add(request.form.get('name'), request.form.get('parent'))
    else:
        raise InvalidArgumentException('Did not find any of the expected keys in POST to /admin/archetypes: {f}'.format(f=request.form))
    return edit_archetypes(search_results)

# Infra

@APP.route('/favicon<rest>/')
def favicon(rest):
    return send_from_directory(os.path.join(APP.root_path, 'static/images/favicon'), 'favicon{rest}'.format(rest=rest))

@APP.route('/charts/cmc/<deck_id>-cmc.png')
def cmc_chart(deck_id):
    return send_file(chart.cmc(int(deck_id)))

@APP.route('/legal_cards.txt')
def legal_cards():
    if os.path.exists('legal_cards.txt'):
        return send_from_directory('.', 'legal_cards.txt')

    return "Not supported yet", 404

@APP.errorhandler(DoesNotExistException)
@APP.errorhandler(exceptions.NotFound)
def not_found(e):
    traceback.print_exception(e, e, None)
    view = NotFound(e)
    return view.page(), 404

@APP.errorhandler(exceptions.InternalServerError)
def internal_server_error(e):
    traceback.print_exception(e, e, None)
    view = InternalServerError(e)
    return view.page(), 500

def init():
    # This makes sure that the method decorators are called.
    import decksite.api as _ # pylint: disable=unused-import

    APP.run(host='0.0.0.0', debug=True)
