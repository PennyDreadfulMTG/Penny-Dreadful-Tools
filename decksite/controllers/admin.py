import datetime
from typing import Any, Dict, List, Optional, Union, cast

import titlecase
from flask import make_response, redirect, request, session, url_for
from flask_babel import gettext
from werkzeug import wrappers

from decksite import APP, auth
from decksite import league as lg
from decksite.data import archetype as archs
from decksite.data import competition as comp
from decksite.data import deck as ds
from decksite.data import match as ms
from decksite.data import news as ns
from decksite.data import person as ps
from decksite.data import rule as rs
from decksite.league import RetireForm
from decksite.views import (Admin, AdminRetire, EditAliases, EditArchetypes, EditLeague,
                            EditMatches, EditNews, EditRules, PlayerNotes, Prizes,
                            RotationChecklist, Unlink)
from magic import rotation
from magic.models import Deck
from shared import dtutil, redis
from shared.container import Container
from shared.pd_exception import InvalidArgumentException
from shared_web.decorators import fill_form


def admin_menu() -> List[Dict[str, str]]:
    m = []
    endpoints = sorted([rule.endpoint for rule in APP.url_map.iter_rules() if 'GET' in rule.methods and rule.rule.startswith('/admin')])
    for endpoint in endpoints:
        name = titlecase.titlecase(endpoint.replace('_', ' ')) if endpoint else 'Admin Home'
        m.append({'name': name, 'endpoint': endpoint, 'url': url_for(endpoint)})
    m.append({'name': gettext('Rotation Speculation'), 'endpoint': 'rotation_speculation'})
    return m

@APP.route('/admin/')
@auth.demimod_required
def admin_home() -> wrappers.Response:
    view = Admin(admin_menu())
    return view.response()

@APP.route('/admin/aliases/')
@auth.admin_required
def edit_aliases() -> str:
    aliases = ps.load_aliases()
    all_people = ps.load_people(order_by_name=True)
    view = EditAliases(aliases, all_people)
    return view.page()

@APP.route('/admin/aliases/', methods=['POST'])
@fill_form('person_id', 'alias')
@auth.admin_required
def post_aliases(person_id: int = None, alias: str = None) -> Union[str, wrappers.Response]:
    if person_id is not None and alias is not None and len(alias) > 0:
        ps.add_alias(person_id, alias)
    return edit_aliases()

@APP.route('/admin/archetypes/')
@auth.demimod_required
def edit_archetypes(search_results: Optional[List[Deck]] = None, q: str = '', notq: str = '') -> wrappers.Response:
    if search_results is None:
        search_results = []
    view = EditArchetypes(archs.load_archetypes_deckless(order_by='a.name'), search_results, q, notq)
    return view.response()

@APP.route('/admin/archetypes/', methods=['POST'])
@auth.demimod_required
def post_archetypes() -> wrappers.Response:
    search_results: List[Deck] = []
    if request.form.get('deck_id') is not None:
        archetype_ids = request.form.getlist('archetype_id')
        # Adjust archetype_ids if we're assigning multiple decks to the same archetype.
        if len(archetype_ids) == 1 and len(request.form.getlist('deck_id')) > 1:
            archetype_ids = archetype_ids * len(request.form.getlist('deck_id'))
        for deck_id in request.form.getlist('deck_id'):
            archetype_id = archetype_ids.pop(0)
            if archetype_id:
                archs.assign(deck_id, archetype_id, auth.person_id())
                redis.clear(f'decksite:deck:{deck_id}')
    elif request.form.get('q') is not None and request.form.get('notq') is not None:
        search_results = ds.load_decks_by_cards(cast(str, request.form.get('q')).splitlines(), cast(str, request.form.get('notq')).splitlines())
    elif request.form.get('find_conflicts') is not None:
        search_results = ds.load_conflicted_decks()
    elif request.form.get('rename_to') is not None:
        archs.rename(cast_int(request.form.get('archetype_id')), cast(str, request.form.get('rename_to')))
    elif request.form.get('new_description') is not None:
        archs.update_description(cast_int(request.form.get('archetype_id')), cast(str, request.form.get('new_description')))
    elif request.form.getlist('archetype_id') is not None and len(request.form.getlist('archetype_id')) == 2:
        archs.move(request.form.getlist('archetype_id')[0], request.form.getlist('archetype_id')[1])
    elif request.form.get('parent') is not None:
        archs.add(cast(str, request.form.get('name')), cast_int(request.form.get('parent')))
    else:
        raise InvalidArgumentException('Did not find any of the expected keys in POST to /admin/archetypes: {f}'.format(f=request.form))
    return edit_archetypes(search_results, request.form.get('q', ''), request.form.get('notq', ''))

@APP.route('/admin/rules/')
@auth.demimod_required
def edit_rules() -> wrappers.Response:
    cnum = rs.num_classified_decks()
    tnum = ds.num_decks(rs.classified_decks_query())
    archetypes = archs.load_archetypes_deckless(order_by='a.name')
    view = EditRules(cnum, tnum, rs.doubled_decks(), rs.mistagged_decks(), rs.overlooked_decks(), rs.load_all_rules(), archetypes, rs.excluded_archetype_info())
    return view.response()

@APP.route('/admin/rules/', methods=['POST'])
@auth.demimod_required
def post_rules() -> wrappers.Response:
    if request.form.get('archetype_id') is not None:
        rs.add_rule(cast_int(request.form.get('archetype_id')))
    else:
        raise InvalidArgumentException('Did not find any of the expected keys in POST to /admin/rules: {f}'.format(f=request.form))
    return edit_rules()

@APP.route('/admin/retire/')
@auth.admin_required
def admin_retire_deck(form: Optional[RetireForm] = None) -> str:
    if form is None:
        form = RetireForm(request.form)
    view = AdminRetire(form)
    return view.page()

@APP.route('/admin/retire/', methods=['POST'])
@auth.admin_required
def do_admin_retire_deck() -> wrappers.Response:
    form = RetireForm(request.form)
    if form.validate():
        d = ds.load_deck(form.entry)
        lg.retire_deck(d)
        return redirect(url_for('admin_retire_deck'))
    return make_response(admin_retire_deck(form))

@APP.route('/admin/matches/')
@auth.admin_required
def edit_matches() -> str:
    view = EditMatches(lg.active_league(should_load_decks=True).decks, lg.load_latest_league_matches())
    return view.page()

@APP.route('/admin/matches/', methods=['POST'])
@auth.admin_required
def post_matches() -> wrappers.Response:
    if request.form.get('match_id'):
        match_id = cast_int(request.form.get('match_id'))
    if request.form.get('action') == 'delete':
        ms.delete_match(match_id)
        return redirect(url_for('edit_matches'))
    left_id = cast_int(request.form.get('left_id'))
    left_games = cast_int(request.form.get('left_games'))
    right_id = cast_int(request.form.get('right_id'))
    right_games = cast_int(request.form.get('right_games'))
    if request.form.get('action') == 'change':
        ms.update_match(match_id, left_id, left_games, right_id, right_games)
    elif request.form.get('action') == 'add':
        ms.insert_match(dtutil.now(), left_id, left_games, right_id, right_games, None, None, None)
    return redirect(url_for('edit_matches'))

@APP.route('/admin/news/')
@auth.admin_required
def edit_news() -> str:
    new_item = Container({'form_date': dtutil.form_date(dtutil.now(dtutil.WOTC_TZ), dtutil.WOTC_TZ), 'title': '', 'url': ''})
    news_items = [new_item] + ns.load_news()
    view = EditNews(news_items)
    return view.page()

@APP.route('/admin/news/', methods=['POST'])
@fill_form('news_id', 'title', 'url')
@auth.admin_required
def post_news(news_id: int, title: str = None, url: str = None, date: str = None) -> wrappers.Response:
    if request.form.get('action') == 'delete':
        ns.delete(news_id)
    else:
        if date is not None and title is not None and url is not None:
            date_dt = dtutil.parse(date, dtutil.FORM_FORMAT, dtutil.WOTC_TZ)
            ns.add_or_update_news(news_id, date_dt, title, url)
    return redirect(url_for('edit_news'))

@APP.route('/admin/prizes/')
def prizes() -> str:
    tournaments_with_prizes = comp.tournaments_with_prizes()
    first_runs = lg.first_runs()
    view = Prizes(tournaments_with_prizes, first_runs)
    return view.page()

@APP.route('/admin/rotation/')
def rotation_checklist() -> str:
    view = RotationChecklist()
    return view.page()

@APP.route('/admin/people/notes/')
@auth.admin_required
def player_notes() -> str:
    notes = ps.load_notes()
    all_people = ps.load_people(order_by_name=True)
    view = PlayerNotes(notes, all_people)
    return view.page()

@APP.route('/admin/people/notes/', methods=['POST'])
@auth.admin_required
def post_player_note() -> wrappers.Response:
    if not request.form.get('person_id') or not request.form.get('note'):
        raise InvalidArgumentException(f'Did not find any of the expected keys in POST to /admin/people/notes: {request.form}')
    creator = ps.load_person_by_discord_id(session['id'])
    ps.add_note(creator.id, request.form['person_id'], request.form['note'])
    return redirect(url_for('player_notes'))

@APP.route('/admin/unlink/')
@auth.admin_required
def unlink(num_affected_people: Optional[int] = None, errors: List[str] = None) -> str:
    all_people = ps.load_people(order_by_name=True)
    view = Unlink(all_people, num_affected_people, errors)
    return view.page()

@APP.route('/admin/unlink/', methods=['POST'])
@auth.admin_required
def post_unlink() -> str:
    n, errors = 0, []
    person_id = request.form.get('person_id')
    if person_id:
        n += ps.unlink_discord(person_id)
    discord_id = request.form.get('discord_id')
    if discord_id:
        try:
            discord_id = int(discord_id)
            n += ps.remove_discord_link(discord_id)
        except ValueError:
            errors.append('Discord ID must be an integer.')
    return unlink(n, errors)

@APP.route('/admin/league/')
@auth.admin_required
def edit_league() -> str:
    view = EditLeague(lg.get_status())
    return view.page()

@APP.route('/admin/league/', methods=['POST'])
@auth.admin_required
def post_league() -> str:
    status = lg.Status.CLOSED if request.form.get('action') == 'close' else lg.Status.OPEN
    lg.set_status(status)
    return edit_league()

def cast_int(param: Optional[Any]) -> int:
    return int(cast(str, param))
