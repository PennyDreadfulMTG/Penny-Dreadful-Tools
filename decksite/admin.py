from typing import Dict, List, Optional

from flask import request, session, url_for

from magic.models import Deck
from decksite import APP, auth
from decksite import league as lg
from decksite.data import archetype as archs
from decksite.data import competition as comp
from decksite.data import deck as ds
from decksite.data import match as ms
from decksite.data import news as ns
from decksite.data import person as ps
from decksite.views import (Admin, EditArchetypes, EditMatches, EditNews,
                            PlayerNotes, Prizes, RotationChecklist, Unlink)
from shared import dtutil, redis
from shared.container import Container
from shared.pd_exception import InvalidArgumentException


def admin_menu() -> List[Dict[str, str]]:
    m = []
    urls = sorted([url_for(rule.endpoint) for rule in APP.url_map.iter_rules() if 'GET' in rule.methods and rule.rule.startswith('/admin')])
    for url in urls:
        name = url.replace('/admin/', '').strip('/')
        name = name if name else 'Admin Home'
        m.append({'name': name, 'url': url})
    return m

@APP.route('/admin/')
@auth.admin_required
def admin_home() -> str:
    view = Admin(admin_menu())
    return view.page()

@APP.route('/admin/archetypes/')
@auth.demimod_required
def edit_archetypes(search_results: Optional[List[Deck]] = None, q: str = '', notq: str = '') -> str:
    if search_results is None:
        search_results = []
    view = EditArchetypes(archs.load_archetypes_deckless(order_by='a.name'), search_results, q, notq)
    return view.page()

@APP.route('/admin/archetypes/', methods=['POST'])
@auth.demimod_required
def post_archetypes() -> str:
    search_results: List[Deck] = []
    if request.form.get('deck_id') is not None:
        archetype_ids = request.form.getlist('archetype_id')
        # Adjust archetype_ids if we're assigning multiple decks to the same archetype.
        if len(archetype_ids) == 1 and len(request.form.getlist('deck_id')) > 1:
            archetype_ids = archetype_ids * len(request.form.getlist('deck_id'))
        for deck_id in request.form.getlist('deck_id'):
            archetype_id = archetype_ids.pop(0)
            if archetype_id:
                archs.assign(deck_id, archetype_id)
                redis.clear(f'decksite:deck:{deck_id}')
    elif request.form.get('q') is not None and request.form.get('notq') is not None:
        search_results = ds.load_decks_by_cards(request.form.get('q').splitlines(), request.form.get('notq').splitlines())
    elif request.form.get('find_conflicts') is not None:
        search_results = ds.load_conflicted_decks()
    elif request.form.get('rename_to') is not None:
        archs.rename(request.form.get('archetype_id'), request.form.get('rename_to'))
    elif request.form.get('new_description') is not None:
        archs.update_description(request.form.get('archetype_id'), request.form.get('new_description'))
    elif request.form.getlist('archetype_id') is not None and len(request.form.getlist('archetype_id')) == 2:
        archs.move(request.form.getlist('archetype_id')[0], request.form.getlist('archetype_id')[1])
    elif request.form.get('parent') is not None:
        archs.add(request.form.get('name'), request.form.get('parent'))
    else:
        raise InvalidArgumentException('Did not find any of the expected keys in POST to /admin/archetypes: {f}'.format(f=request.form))
    return edit_archetypes(search_results, request.form.get('q', ''), request.form.get('notq', ''))

@APP.route('/admin/matches/')
@auth.admin_required
def edit_matches() -> str:
    view = EditMatches(lg.load_latest_league_matches())
    return view.page()

@APP.route('/admin/matches/', methods=['POST'])
@auth.admin_required
def post_matches() -> str:
    if request.form.get('action') == 'change':
        lg.update_match(request.form.get('match_id'), request.form.get('left_id'), request.form.get('left_games'), request.form.get('right_id'), request.form.get('right_games'))
    elif request.form.get('action') == 'delete':
        lg.delete_match(request.form.get('match_id'))
    elif request.form.get('action') == 'add':
        ms.insert_match(dtutil.now(), request.form.get('left_id'), request.form.get('left_games'), request.form.get('right_id'), request.form.get('right_games'), None, None, None)
    return edit_matches()

@APP.route('/admin/news/')
@auth.admin_required
def edit_news() -> str:
    new_item = Container({'form_date': dtutil.form_date(dtutil.now(dtutil.WOTC_TZ), dtutil.WOTC_TZ), 'title': '', 'url': ''})
    news_items = [new_item] + ns.load_news()
    view = EditNews(news_items)
    return view.page()

@APP.route('/admin/news/', methods=['POST'])
@auth.admin_required
def post_news() -> str:
    if request.form.get('action') == 'delete':
        ns.delete(request.form.get('id'))
    else:
        date = dtutil.parse(request.form.get('date'), dtutil.FORM_FORMAT, dtutil.WOTC_TZ)
        ns.add_or_update_news(request.form.get('id'), date, request.form.get('title'), request.form.get('url'))
    return edit_news()

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
    all_people = ps.load_people(order_by='p.mtgo_username')
    view = PlayerNotes(notes, all_people)
    return view.page()

@APP.route('/admin/people/notes/', methods=['POST'])
@auth.admin_required
def post_player_note() -> str:
    creator = ps.load_person_by_discord_id(session['id'])
    ps.add_note(creator.id, request.form.get('subject_id'), request.form.get('note'))
    return player_notes()

@APP.route('/admin/unlink/')
@auth.admin_required
def unlink(num_affected_people: Optional[int] = None) -> str:
    all_people = ps.load_people(order_by='p.mtgo_username')
    view = Unlink(all_people, num_affected_people)
    return view.page()

@APP.route('/admin/unlink/', methods=['POST'])
@auth.admin_required
def post_unlink() -> str:
    n = 0
    person_id = request.form.get('person_id')
    if person_id:
        n += ps.unlink_discord(person_id)
    discord_id = request.form.get('discord_id')
    if discord_id:
        n += ps.remove_discord_link(discord_id)
    return unlink(n)
