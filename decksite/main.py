import os
import traceback
import urllib.parse

from flask import (abort, g, make_response, redirect, request, send_file,
                   send_from_directory, session, url_for)
from github.GithubException import GithubException
from werkzeug import exceptions

from decksite import league as lg
from decksite import APP, auth, deck_name
from decksite.cache import cached
from decksite.charts import chart
from decksite.data import archetype as archs
from decksite.data import card as cs
from decksite.data import competition as comp
from decksite.data import deck as ds
from decksite.data import news as ns
from decksite.data import person as ps
from decksite.data import query
from decksite.league import ReportForm, RetireForm, SignUpForm
from decksite.views import (About, AboutPdm, AddForm, Admin, Archetype,
                            Archetypes, Bugs, Card, Cards, Competition,
                            Competitions, Deck, Decks, EditArchetypes,
                            EditMatches, EditNews, Home, InternalServerError,
                            LeagueInfo, LinkAccounts, News, NotFound, People,
                            Person, Prizes, Report, Resources, Retire,
                            Rotation, RotationChanges, RotationChecklist,
                            Season, Seasons, SignUp, TournamentHosting,
                            TournamentLeaderboards, Tournaments, Unauthorized)
from magic import card as mc
from magic import oracle
from shared import dtutil, perf, repo
from shared.container import Container
from shared.pd_exception import (DoesNotExistException,
                                 InvalidArgumentException,
                                 InvalidDataException)

# Decks

@APP.route('/')
@cached()
def home():
    view = Home(ns.load_news(max_items=10), ds.load_decks(limit='LIMIT 50'), cs.played_cards())
    return view.page()

@APP.route('/decks/')
@cached()
def decks():
    view = Decks(ds.load_decks(limit='LIMIT 500'))
    return view.page()

@APP.route('/decks/<deck_id>/')
@auth.logged
def deck(deck_id):
    d = ds.load_deck(deck_id)
    if auth.discord_id() and auth.logged_person() is None and not d.is_person_associated():
        ps.associate(d, auth.discord_id())
        p = ps.load_person_by_discord_id(auth.discord_id())
        auth.log_person(p.id, p.name)

    view = Deck(d, auth.logged_person())
    return view.page()

@APP.route('/seasons/')
@cached()
def seasons():
    view = Seasons()
    return view.page()

@APP.route('/seasons/<season_id>/')
@APP.route('/seasons/<season_id>/<deck_type>/')
@cached()
def season(season_id, deck_type=None):
    league_only = deck_type == 'league'
    view = Season(ds.load_season(season_id, league_only), league_only)
    return view.page()

@APP.route('/people/')
@cached()
def people():
    view = People(ps.load_people())
    return view.page()

@APP.route('/people/<person_id>/')
@cached()
def person(person_id):
    p = ps.load_person(person_id)
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
        c = cs.load_card(oracle.valid_name(urllib.parse.unquote_plus(name)))
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
    a = archs.load_archetype(archetype_id.replace('+', ' '))
    view = Archetype(a, archs.load_archetypes_deckless_for(a.id), archs.load_matchups(a.id))
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
@cached()
def tournament_leaderboards():
    leaderboards = comp.leaderboards()
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

@APP.route('/rotation/')
@cached()
def rotation():
    view = Rotation()
    return view.page()

@APP.route('/export/<deck_id>/')
@auth.logged
def export(deck_id):
    d = ds.load_deck(deck_id)
    if d.is_in_current_run():
        if not auth.logged_person() or auth.logged_person() != d.person_id:
            abort(403)
    safe_name = deck_name.file_name(d)
    return (mc.to_mtgo_format(str(d)), 200, {'Content-type': 'text/plain; charset=utf-8', 'Content-Disposition': 'attachment; filename={name}.txt'.format(name=safe_name)})

@APP.route('/link')
@auth.login_required
def link():
    view = LinkAccounts()
    return view.page()

@APP.route('/link', methods=['POST'])
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
@auth.logged
def signup(form=None):
    if form is None:
        form = SignUpForm(request.form, auth.logged_person_mtgo_username())
    view = SignUp(form)
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

@APP.route('/report/')
@auth.logged
def report(form=None):
    if form is None:
        form = ReportForm(request.form, request.cookies.get('deck_id', ''), auth.logged_person())
    view = Report(form, auth.logged_person())
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
def rotation_changes():
    view = RotationChanges(*oracle.last_pd_rotation_changes(), cs.playability())
    return view.page()

@APP.route('/rotation/speculation/')
def rotation_speculation():
    view = RotationChanges(oracle.if_todays_prices(out=False), oracle.if_todays_prices(out=True), cs.playability(), speculation=True)
    return view.page()

# Admin

@APP.route('/admin/')
@auth.admin_required
def admin_home():
    urls = sorted([url_for(rule.endpoint) for rule in APP.url_map.iter_rules() if 'GET' in rule.methods and rule.rule.startswith('/admin')])
    view = Admin(urls)
    return view.page()

@APP.route('/querytappedout/')
def deckcycle_tappedout():
    from decksite.scrapers import tappedout
    if not tappedout.is_authorised():
        tappedout.login()
    tappedout.scrape()
    return home()

@APP.route('/admin/archetypes/')
@auth.admin_required
def edit_archetypes(search_results=None):
    if search_results is None:
        search_results = []
    view = EditArchetypes(archs.load_archetypes_deckless(order_by='a.name'), search_results)
    return view.page()

@APP.route('/admin/archetypes/', methods=['POST'])
@auth.admin_required
def post_archetypes():
    search_results = []
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
        search_results = ds.load_decks_by_cards(request.form.get('q').splitlines())
    elif request.form.getlist('archetype_id') is not None and len(request.form.getlist('archetype_id')) == 2:
        archs.move(request.form.getlist('archetype_id')[0], request.form.getlist('archetype_id')[1])
    elif request.form.get('parent') is not None:
        archs.add(request.form.get('name'), request.form.get('parent'))
    else:
        raise InvalidArgumentException('Did not find any of the expected keys in POST to /admin/archetypes: {f}'.format(f=request.form))
    return edit_archetypes(search_results)

@APP.route('/admin/matches/')
@auth.admin_required
def edit_matches():
    view = EditMatches(lg.load_latest_league_matches())
    return view.page()

@APP.route('/admin/matches/', methods=['POST'])
@auth.admin_required
def post_matches():
    if request.form.get('match_id') is not None:
        lg.delete_match(request.form.get('match_id'))
    return edit_matches()

@APP.route('/admin/news/')
@auth.admin_required
def edit_news():
    new_item = Container({'form_date': dtutil.form_date(dtutil.now(dtutil.WOTC_TZ), dtutil.WOTC_TZ), 'title': '', 'body': ''})
    news_items = [new_item] + ns.load_news()
    view = EditNews(news_items)
    return view.page()

@APP.route('/admin/news/', methods=['POST'])
@auth.admin_required
def post_news():
    print(request.form)
    if request.form.get('action') == 'delete':
        ns.delete(request.form.get('id'))
    else:
        date = dtutil.parse(request.form.get('date'), dtutil.FORM_FORMAT, dtutil.WOTC_TZ)
        ns.add_or_update_news(request.form.get('id'), date, request.form.get('title'), request.form.get('body'))
    return edit_news()

@APP.route('/admin/prizes/')
def prizes():
    where = """
            cs.competition_type_id
        IN
            ({competition_type_id_select})
        AND
            c.start_date > (UNIX_TIMESTAMP(NOW() - INTERVAL 26 WEEK))
        """.format(competition_type_id_select=query.competition_type_id_select('Gatherling'))
    comps = comp.load_competitions(where)
    first_runs = lg.first_runs()
    view = Prizes(comps, first_runs)
    return view.page()

@APP.route('/admin/rotation/')
def rotation_checklist():
    view = RotationChecklist()
    return view.page()

# OAuth

@APP.route('/authenticate/')
def authenticate():
    target = request.args.get('target')
    authorization_url, state = auth.setup_authentication()
    session['oauth2_state'] = state
    if target is not None:
        session['target'] = target
    return redirect(authorization_url)

@APP.route('/authenticate/callback/')
def authenticate_callback():
    if request.values.get('error'):
        return redirect(url_for('unauthorized', error=request.values['error']))
    auth.setup_session(request.url)
    url = session.get('target')
    if url is None:
        url = url_for('home')
    session['target'] = None
    return redirect(url)

@APP.route('/unauthorized/')
def unauthorized(error=None):
    view = Unauthorized(error)
    return view.page()

@APP.route('/logout/')
def logout():
    auth.logout()
    target = request.args.get('target', 'home')
    if bool(urllib.parse.urlparse(target).netloc):
        return redirect(target)
    return redirect(url_for(target))

# Infra

@APP.route('/robots.txt')
def robots():
    return send_from_directory(os.path.join(APP.root_path, 'static'), 'robots.txt')

@APP.route('/favicon<rest>/')
def favicon(rest):
    return send_from_directory(os.path.join(APP.root_path, 'static/images/favicon'), 'favicon{rest}'.format(rest=rest))

@APP.route('/charts/cmc/<deck_id>-cmc.png')
def cmc_chart(deck_id):
    return send_file(chart.cmc(int(deck_id)))

@APP.route('/charts/archetypes/<competition_id>-archetypes-sparkline.png')
def archetype_sparkline_chart(competition_id):
    return send_file(chart.archetypes_sparkline(int(competition_id)))

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
    path = request.path
    try:
        repo.create_issue('500 error at {path}\n {e}'.format(path=path, e=e), session.get('id', 'logged_out'), 'decksite', 'PennyDreadfulMTG/perf-reports', exception=e)
    except GithubException:
        print("Github error")
    view = InternalServerError(e)
    return view.page(), 500

@APP.before_request
def before_request():
    g.p = perf.start()


@APP.teardown_request
def teardown_request(response):
    perf.check(g.p, 'slow_page', request.path, 'decksite')
    return response

def init(debug=True, port=None):
    """This method is only called when initializing the dev server.  uwsgi (prod) doesn't call this method"""
    APP.run(host='0.0.0.0', debug=debug, port=port)
