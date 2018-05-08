import logging
import os
import urllib.parse
from typing import Optional, Tuple

from flask import (Response, abort, g, make_response, redirect, request,
                   send_file, send_from_directory, session, url_for)

from decksite import APP, SEASONS, auth, deck_name, get_season_id
from decksite import league as lg
from decksite.cache import cached
from decksite.charts import chart
from decksite.data import archetype as archs
from decksite.data import card as cs
from decksite.data import competition as comp
from decksite.data import deck as ds
from decksite.data import news as ns
from decksite.data import person as ps
from decksite.league import DeckCheckForm, ReportForm, RetireForm, SignUpForm
from decksite.views import (About, AboutPdm, AddForm, Archetype, Archetypes,
                            Bugs, Card, Cards, CommunityGuidelines,
                            Competition, Competitions, Deck, DeckCheck, Decks,
                            Faqs, Home, LeagueInfo, LinkAccounts, News, People,
                            Person, Report, Resources, Retire, Rotation,
                            RotationChanges, Season, Seasons, SignUp,
                            TournamentHosting, TournamentLeaderboards,
                            Tournaments)
from magic import card as mc
from magic import oracle
from shared import perf
from shared.pd_exception import DoesNotExistException, InvalidDataException
from shared_web import oauth

# Decks

@APP.route('/')
@cached()
def home():
    view = Home(ns.load_news(max_items=10), ds.load_decks(limit='LIMIT 50'), cs.played_cards(season_id=get_season_id()))
    return view.page()

@APP.route('/decks/')
@SEASONS.route('/decks/')
@cached()
def decks():
    view = Decks(ds.load_decks(limit='LIMIT 500', season_id=get_season_id()))
    return view.page()

@APP.route('/decks/<deck_id>/')
@auth.load_person
def deck(deck_id):
    d = ds.load_deck(deck_id)
    view = Deck(d, auth.person_id(), auth.discord_id())
    return view.page()

@APP.route('/seasons/')
@cached()
def seasons():
    view = Seasons()
    return view.page()

@SEASONS.route('/')
@SEASONS.route('/<deck_type>/')
@cached()
def season(deck_type=None):
    league_only = deck_type == 'league'
    view = Season(ds.load_season(get_season_id(), league_only), league_only)
    return view.page()

@APP.route('/people/')
@SEASONS.route('/people/')
@cached()
def people():
    view = People(ps.load_people(season_id=get_season_id()))
    return view.page()

@APP.route('/people/<person_id>/')
@SEASONS.route('/people/<person_id>/')
@cached()
def person(person_id):
    p = ps.load_person(person_id, season_id=get_season_id())
    played_cards = cs.played_cards_by_person(p.id, get_season_id())
    only_played_cards = cs.only_played_by(p.id, get_season_id())
    view = Person(p, played_cards, only_played_cards)
    return view.page()

@APP.route('/cards/')
@SEASONS.route('/cards/')
@cached()
def cards():
    view = Cards(cs.played_cards(season_id=get_season_id()))
    return view.page()

@APP.route('/cards/<path:name>/')
@SEASONS.route('/cards/<path:name>/')
@cached()
def card(name):
    try:
        c = cs.load_card(oracle.valid_name(urllib.parse.unquote_plus(name)), season_id=get_season_id())
        view = Card(c)
        return view.page()
    except InvalidDataException as e:
        raise DoesNotExistException(e)

@APP.route('/competitions/')
@SEASONS.route('/competitions/')
@cached()
def competitions():
    view = Competitions(comp.load_competitions(season_id=get_season_id()))
    return view.page()

@APP.route('/competitions/<competition_id>/')
@cached()
def competition(competition_id):
    view = Competition(comp.load_competition(competition_id))
    return view.page()

@APP.route('/archetypes/')
@SEASONS.route('/archetypes/')
@cached()
def archetypes():
    view = Archetypes(archs.load_archetypes_deckless(season_id=get_season_id()))
    return view.page()

@APP.route('/archetypes/<archetype_id>/')
@SEASONS.route('/archetypes/<archetype_id>/')
@cached()
def archetype(archetype_id):
    season_id = get_season_id()
    a = archs.load_archetype(archetype_id.replace('+', ' '), season_id=season_id)
    view = Archetype(a, archs.load_archetypes_deckless_for(a.id, season_id=season_id), archs.load_matchups(a.id, season_id=season_id), season_id)
    return view.page()

@APP.route('/tournaments/')
def tournaments():
    view = Tournaments()
    return view.page()

@APP.route('/tournaments/hosting/')
@cached()
def hosting():
    view = TournamentHosting()
    return view.page()

@APP.route('/tournaments/leaderboards/')
@SEASONS.route('/tournaments/leaderboards/')
@cached()
def tournament_leaderboards():
    leaderboards = comp.leaderboards(season_id=get_season_id())
    view = TournamentLeaderboards(leaderboards)
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
    if 'tappedout' in url:
        import decksite.scrapers.tappedout
        try:
            deck_id = decksite.scrapers.tappedout.scrape_url(url).id
        except InvalidDataException as e:
            error = e.args[0]
    else:
        error = 'Deck host is not supported.'
    if error is not None:
        view = AddForm()
        view.error = error
        return view.page(), 409
    return redirect(url_for('deck', deck_id=deck_id))

@APP.route('/about/')
@cached()
def about_pdm():
    view = AboutPdm()
    return view.page()

@APP.route('/gp/')
@cached()
def about_gp():
    return make_response(redirect(url_for('about', src='gp')))

@APP.route('/about/pd/')
@cached()
def about():
    view = About(request.args.get('src'))
    return view.page()

@APP.route('/faqs/')
@cached()
def faqs():
    view = Faqs()
    return view.page()

@APP.route('/community/guidelines/')
@cached()
def community_guidelines():
    view = CommunityGuidelines()
    return view.page()

@APP.route('/rotation/')
@cached()
def rotation():
    view = Rotation()
    return view.page()

@APP.route('/export/<deck_id>/')
@auth.load_person
def export(deck_id):
    d = ds.load_deck(deck_id)
    if d.is_in_current_run():
        if not auth.person_id() or auth.person_id() != d.person_id:
            abort(403)
    safe_name = deck_name.file_name(d)
    return (mc.to_mtgo_format(str(d)), 200, {'Content-type': 'text/plain; charset=utf-8', 'Content-Disposition': 'attachment; filename={name}.txt'.format(name=safe_name)})

@APP.route('/link/')
@auth.login_required
def link():
    view = LinkAccounts()
    return view.page()

@APP.route('/link/', methods=['POST'])
@auth.login_required
def link_post():
    view = LinkAccounts()
    return view.page()

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

@APP.route('/news/')
@cached()
def news():
    news_items = ns.load_news()
    view = News(news_items)
    return view.page()

# League

@APP.route('/league/')
def league():
    view = LeagueInfo()
    return view.page()

@APP.route('/league/current/')
@cached()
def current_league():
    return competition(lg.active_league().id)

@APP.route('/signup/')
@auth.load_person
def signup(form=None):
    if form is None:
        form = SignUpForm(request.form, auth.person_id(), auth.mtgo_username())
    view = SignUp(form, auth.person_id())
    return view.page()

@APP.route('/signup/', methods=['POST'])
@cached()
def add_signup():
    form = SignUpForm(request.form)
    if form.validate():
        d = lg.signup(form)
        response = make_response(redirect(url_for('deck', deck_id=d.id)))
        response.set_cookie('deck_id', str(d.id))
        return response
    return signup(form)

@APP.route('/deckcheck/')
@auth.load_person
def deck_check(form=None):
    if form is None:
        form = DeckCheckForm(request.form, auth.person_id(), auth.mtgo_username())
    view = DeckCheck(form, auth.person_id())
    return view.page()

@APP.route('/deckcheck/', methods=['POST'])
@cached()
def do_deck_check():
    form = DeckCheckForm(request.form)
    form.validate()
    return deck_check(form)



@APP.route('/report/')
@auth.load_person
def report(form=None):
    if form is None:
        form = ReportForm(request.form, request.cookies.get('deck_id', ''), auth.person_id())
    view = Report(form, auth.person_id())
    return view.page()

@APP.route('/report/', methods=['POST'])
def add_report():
    form = ReportForm(request.form)
    if form.validate() and lg.report(form):
        response = make_response(redirect(url_for('deck', deck_id=form.entry)))
        response.set_cookie('deck_id', form.entry)
        return response
    return report(form)

@APP.route('/retire/')
@auth.login_required
def retire(form=None):
    if form is None:
        form = RetireForm(request.form, request.cookies.get('deck_id', ''), session.get('id'))
    view = Retire(form)
    return view.page()

@APP.route('/retire/', methods=['POST'])
@auth.login_required
def do_claim():
    form = RetireForm(request.form, discord_user=session.get('id'))
    if form.validate():
        d = ds.load_deck(form.entry)
        ps.associate(d, session['id'])
        lg.retire_deck(d)
        return redirect(url_for('signup'))
    return retire(form)

@APP.route('/rotation/changes/')
@SEASONS.route('/rotation/changes/')
def rotation_changes():
    view = RotationChanges(*oracle.pd_rotation_changes(get_season_id()), cs.playability())
    return view.page()

@APP.route('/rotation/speculation/')
def rotation_speculation():
    view = RotationChanges(oracle.if_todays_prices(out=False), oracle.if_todays_prices(out=True), cs.playability(), speculation=True)
    return view.page()

# OAuth

@APP.route('/authenticate/')
def authenticate():
    target = request.args.get('target')
    authorization_url, state = oauth.setup_authentication()
    session['oauth2_state'] = state
    if target is not None:
        session['target'] = target
    return redirect(authorization_url)

@APP.route('/authenticate/callback/')
def authenticate_callback():
    if request.values.get('error'):
        return redirect(url_for('unauthorized', error=request.values['error']))
    oauth.setup_session(request.url)
    url = session.get('target')
    if url is None:
        url = url_for('home')
    session['target'] = None
    return redirect(url)

# Infra

@APP.route('/robots.txt')
def robots():
    return send_from_directory(os.path.join(APP.root_path, 'static'), 'robots.txt')

@APP.route('/favicon<rest>')
def favicon(rest: str) -> Response:
    return send_from_directory(os.path.join(APP.root_path, 'static/images/favicon'), 'favicon{rest}'.format(rest=rest))

@APP.route('/charts/cmc/<deck_id>-cmc.png')
def cmc_chart(deck_id: int) -> Response:
    return send_file(chart.cmc(int(deck_id)))

@APP.route('/charts/archetypes/<competition_id>-archetypes-sparkline.png')
def archetype_sparkline_chart(competition_id: int) -> Response:
    return send_file(chart.archetypes_sparkline(int(competition_id)))

@APP.route('/legal_cards.txt')
def legal_cards() -> Tuple[str, int]:
    if os.path.exists('legal_cards.txt'):
        return send_from_directory('.', 'legal_cards.txt')
    return 'Not supported yet', 404

@APP.before_request
def before_request() -> None:
    g.p = perf.start()

@APP.teardown_request
def teardown_request(response: Response) -> Response:
    if g.get('p') is not None:
        perf.check(g.p, 'slow_page', request.path, 'decksite')
    return response

def init(debug: bool = True, port: Optional[int] = None) -> None:
    """This method is only called when initializing the dev server.  uwsgi (prod) doesn't call this method"""
    APP.logger.setLevel(logging.INFO) # pylint: disable=no-member,no-name-in-module
    APP.run(host='0.0.0.0', debug=debug, port=port)

APP.register_blueprint(SEASONS)
