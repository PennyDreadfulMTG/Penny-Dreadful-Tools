import logging
import os
import urllib.parse
from typing import Optional, Union

from flask import (Response, abort, g, make_response, redirect, request,
                   send_file, session, url_for)
from requests.exceptions import RequestException
from werkzeug.exceptions import InternalServerError

from decksite import APP, SEASONS, auth, deck_name, get_season_id
from decksite import league as lg
from decksite.cache import cached
from decksite.charts import chart
from decksite.data import achievements as achs
from decksite.data import archetype as archs
from decksite.data import card as cs
from decksite.data import competition as comp
from decksite.data import deck as ds
from decksite.data import news as ns
from decksite.data import person as ps
from decksite.database import db
from decksite.league import DeckCheckForm, ReportForm, RetireForm, SignUpForm
from decksite.views import (About, AboutPdm, Achievements, AddForm, Archetype,
                            Archetypes, Bugs, Card, Cards, CommunityGuidelines,
                            Competition, Competitions, Deck, DeckCheck, Decks,
                            Faqs, Home, LeagueInfo, LinkAccounts, News, People,
                            Person, Report, Resources, Retire, Rotation,
                            RotationChanges, Season, Seasons, SignUp,
                            TournamentHosting, TournamentLeaderboards,
                            Tournaments)
from magic import card as mc
from magic import image_fetcher, oracle
from shared import perf
from shared.pd_exception import (DoesNotExistException, InvalidDataException,
                                 TooFewItemsException)


@APP.route('/')
@cached()
def home():
    view = Home(ns.all_news(max_items=10), ds.latest_decks(), cs.load_cards(season_id=get_season_id()))
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
    if deck_type not in [None, 'league']:
        raise DoesNotExistException('Unrecognized deck_type: `{deck_type}`'.format(deck_type=deck_type))
    league_only = deck_type == 'league'
    view = Season(ds.load_season(get_season_id(), league_only), league_only)
    return view.page()

@APP.route('/people/')
@SEASONS.route('/people/')
@cached()
def people() -> str:
    view = People(ps.load_people(season_id=get_season_id()))
    return view.page()

@APP.route('/people/<person_id>/')
@SEASONS.route('/people/<person_id>/')
@cached()
def person(person_id):
    p = ps.load_person_by_id_or_mtgo_username(person_id, season_id=get_season_id())
    person_cards = cs.load_cards(person_id=p.id, season_id=get_season_id())
    only_played_cards = []
    view = Person(p, person_cards, only_played_cards)
    return view.page()

@APP.route('/achievements/')
@SEASONS.route('/achievements/')
def achievements():
    username = auth.mtgo_username()
    p = None
    if username is not None:
        p = ps.load_person_by_mtgo_username(username, season_id=get_season_id())
    view = Achievements(achs.load_achievements(p, season_id=get_season_id()))
    return view.page()

@APP.route('/person/achievements/')
def achievements_redirect() -> Response:
    return redirect(url_for('achievements'))

@APP.route('/cards/')
@SEASONS.route('/cards/')
@cached()
def cards() -> str:
    view = Cards(cs.load_cards(season_id=get_season_id()))
    return view.page()

@APP.route('/cards/<path:name>/')
@SEASONS.route('/cards/<path:name>/')
@cached()
def card(name: str) -> str:
    try:
        c = cs.load_card(oracle.valid_name(urllib.parse.unquote_plus(name)), season_id=get_season_id())
        view = Card(c)
        return view.page()
    except InvalidDataException as e:
        raise DoesNotExistException(e)

@APP.route('/competitions/')
@SEASONS.route('/competitions/')
@cached()
def competitions() -> str:
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
def archetypes() -> str:
    season_id = get_season_id()
    deckless_archetypes = archs.load_archetypes_deckless(season_id=season_id)
    all_matchups = archs.load_all_matchups(season_id=season_id)
    view = Archetypes(deckless_archetypes, all_matchups)
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
def tournaments() -> str:
    view = Tournaments()
    return view.page()

@APP.route('/tournaments/hosting/')
@cached()
def hosting() -> str:
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
@cached()
def add_form():
    view = AddForm()
    return view.page()

@APP.route('/add/', methods=['POST'])
def add_deck():
    url = request.form['url']
    error = None
    if 'tappedout' in url:
        import decksite.scrapers.tappedout
        try:
            deck_id = decksite.scrapers.tappedout.scrape_url(url).id
        except (InvalidDataException, RequestException) as e:
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
    news_items = ns.all_news()
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
def deck_check(form: Optional[DeckCheckForm] = None) -> str:
    if form is None:
        form = DeckCheckForm(request.form, auth.person_id(), auth.mtgo_username())
    view = DeckCheck(form, auth.person_id())
    return view.page()

@APP.route('/deckcheck/', methods=['POST'])
@cached()
def do_deck_check() -> str:
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
def retire_deck() -> Union[str, Response]:
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

@APP.route('/charts/cmc/<deck_id>-cmc.png')
def cmc_chart(deck_id: int) -> Response:
    return send_file(chart.cmc(int(deck_id)))

@APP.route('/discord/')
def discord() -> Response:
    return redirect('https://discord.gg/RxhTEEP')

@APP.route('/image/<path:c>/')
def image(c: str = '') -> Response:
    names = c.split('|')
    try:
        requested_cards = oracle.load_cards(names)
        path = image_fetcher.download_image(requested_cards)
        if path is None:
            raise InternalServerError(f'Failed to get image for {c}') # type: ignore
        return send_file(os.path.abspath(path)) # Send abspath to work around monolith root versus web root.
    except TooFewItemsException as e:
        print(e)
        if len(names) == 1:
            return redirect(f'https://api.scryfall.com/cards/named?exact={c}&format=image', code=303)
        return '', 400

@APP.route('/banner/<seasonnum>.png')
def banner(seasonnum: str) -> Response:
    nice_path = os.path.join(APP.static_folder, 'images', 'banners', f'{seasonnum}.png')
    if os.path.exists(nice_path):
        return send_file(os.path.abspath(nice_path))
    cardnames = ['Enter the Unknown', 'Unknown Shores', 'Peer through Depths']
    background = 'Enter the Infinite'
    if seasonnum == '0':
        cardnames = ['Parallax Wave', 'Treasure Cruise', 'Duress', 'Chain Lightning', 'Rofellos, Llanowar Emissary ', 'Thawing Glaciers', 'Temur Ascendancy']
        background = 'Lake of the Dead'
    elif seasonnum == '1':
        cardnames = ['Mother of Runes', 'Treasure Cruise', 'Duress', 'Lightning Strike', 'Elvish Mystic', 'Fleecemane Lion', 'Vivid Marsh']
        background = 'Dark Ritual'
    elif seasonnum == '2':
        cardnames = ['Frantic Search', 'Hymn to Tourach', "Nevinyrral's Disk", 'Winds of Rath', 'Slagstorm', 'Rise from the Tides', 'Cloudpost']
        background = 'Fact or Fiction'
    elif seasonnum == '3':
        cardnames = ['Shrine of Burning Rage', 'Terramorphic Expanse', 'Parallax Wave', 'Kambal, Consul of Allocation', 'Memory Lapse', 'Magister of Worth', 'Tendrils of Agony']
        background = 'Tidehollow Sculler'
    elif seasonnum == '4':
        cardnames = ['Hymn to Tourach', 'Emerge Unscathed', 'Ordeal of Heliod', 'Lightning Strike', 'Cruel Edict', 'Lagonna-Band Trailblazer', 'Vivid Creek']
        background = 'Vivid Creek'
    elif seasonnum == '5':
        cardnames = ['Dark Ritual', 'Cabal Ritual', 'Pyroclasm', 'Cursed Scroll', 'Necropotence', 'Harmonize', 'Precursor Golem']
        background = 'Boompile'
    elif seasonnum == '6':
        cardnames = ['Chain Lightning', 'Compulsive Research', 'Bogardan Hellkite', 'Grand Coliseum', 'Cartouche of Solidarity', 'Lagonna-Band Trailblazer', 'Felidar Guardian']
        background = 'Parallax Wave'


    path = image_fetcher.generate_banner(cardnames, background)
    return send_file(os.path.abspath(path))

@APP.before_request
def before_request() -> None:
    g.p = perf.start()

@APP.teardown_request
def teardown_request(response: Response) -> Response:
    if g.get('p') is not None:
        perf.check(g.p, 'slow_page', request.path, 'decksite')
    db().close()
    return response

def init(debug: bool = True, port: Optional[int] = None) -> None:
    """This method is only called when initializing the dev server.  uwsgi (prod) doesn't call this method"""
    APP.logger.setLevel(logging.INFO) # pylint: disable=no-member,no-name-in-module
    APP.run(host='0.0.0.0', debug=debug, port=port)

APP.register_blueprint(SEASONS)
