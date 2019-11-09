import datetime
from math import ceil
from typing import List, Optional, cast

from flask import Response, request, session, url_for

from decksite import APP, auth, league
from decksite.data import archetype as archs
from decksite.data import card as cs
from decksite.data import competition as comp
from decksite.data import deck, match
from decksite.data import person as ps
from decksite.data import query
from decksite.data import rule as rs
from decksite.data.achievements import Achievement
from decksite.prepare import prepare_decks
from decksite.views import DeckEmbed
from magic import oracle, rotation
from magic.decklist import parse_line
from magic.models import Deck
from shared import configuration, dtutil, guarantee, redis
from shared.pd_exception import (DoesNotExistException, InvalidDataException,
                                 TooManyItemsException)
from shared_web import template
from shared_web.api import generate_error, return_json, validate_api_key
from shared_web.decorators import fill_args, fill_form


@APP.route('/api/decks/')
def decks_api() -> Response:
    """
    Grab a slice of results from a 0-indexed resultset of decks.
    Input:
        {
            'archetypeId': <int?>,
            'cardName': <str?>,
            'competitionId': <int?>,
            'personId': <int?>,
            'deckType': <'league'|'tournament'|'all'>,
            'page': <int>,
            'pageSize': <int>,
            'personId': <int?>,
            'sortBy': <str>,
            'sortOrder': <'ASC'|'DESC'>,
            'seasonId': <int|'all'>
        }
    Output:
        {
            'page': <int>,
            'pages': <int>,
            'decks': [<deck>]
        }
    """
    if not request.args.get('sortBy') and request.args.get('competitionId'):
        sort_by = 'top8'
        sort_order = 'ASC'
    elif not request.args.get('sortBy'):
        sort_by = 'date'
        sort_order = 'DESC'
    else:
        sort_by = str(request.args.get('sortBy'))
        sort_order = str(request.args.get('sortOrder'))
    assert sort_order in ['ASC', 'DESC']
    order_by = query.decks_order_by(sort_by, sort_order)
    page_size = int(request.args.get('pageSize', 20))
    page = int(request.args.get('page', 0))
    start = page * page_size
    limit = f'LIMIT {start}, {page_size}'
    if request.args.get('competitionId'):
        season_id = 'all' # Don't restrict by season if we're loading something with a date by its id.
    else:
        season_id = rotation.season_id(str(request.args.get('seasonId')), None)
    where = query.decks_where(request.args, session.get('person_id'))
    total = deck.load_decks_count(where=where, season_id=season_id)
    pages = max(ceil(total / page_size) - 1, 0) # 0-indexed
    ds = deck.load_decks(where=where, order_by=order_by, limit=limit, season_id=season_id)
    prepare_decks(ds)
    r = {'page': page, 'pages': pages, 'decks': ds}
    resp = return_json(r, camelize=True)
    resp.set_cookie('page_size', str(page_size))
    return resp

@APP.route('/api/decks/<int:deck_id>')
def deck_api(deck_id: int) -> Response:
    blob = deck.load_deck(deck_id)
    return return_json(blob)

@APP.route('/api/randomlegaldeck')
def random_deck_api() -> Response:
    blob = league.random_legal_deck()
    if blob is None:
        return return_json({'error': True, 'msg': 'No legal decks could be found'})
    blob['url'] = url_for('deck', deck_id=blob['id'], _external=True)
    return return_json(blob)

@APP.route('/api/competitions/')
def competitions_api() -> Response:
    # Don't send competitions with any decks that do not have their correct archetype to third parties otherwise they
    # will store it and be wrong forever.
    comps = comp.load_competitions(having='num_reviewed = num_decks', should_load_decks=True)
    r = []
    for c in comps:
        if c.decks:
            cr = {}
            cr['id'] = c.id
            cr['name'] = c.name
            cr['url'] = url_for('competition_api', competition_id=c.id, _external=True)
            r.append(cr)
    return return_json(r) # type: ignore

@APP.route('/api/competitions/<competition_id>')
def competition_api(competition_id: int) -> Response:
    return return_json(comp.load_competition(competition_id))

@APP.route('/api/league')
def league_api() -> Response:
    lg = league.active_league(should_load_decks=True)
    pdbot = request.form.get('api_token', None) == configuration.get('pdbot_api_token')
    if not pdbot:
        lg.decks = [d for d in lg.decks if not d.is_in_current_run()]
    return return_json(lg)

@APP.route('/api/person/<person>')
@fill_args('season_id')
def person_api(person: str, season_id: int = -1) -> Response:
    if season_id == -1:
        season_id = rotation.current_season_num()
    try:
        p = ps.load_person_by_discord_id_or_username(person, season_id)
        p.decks_url = url_for('person_decks_api', person=person, season_id=season_id)
        p.head_to_head = url_for('person_h2h_api', person=person, season_id=season_id)
        return return_json(p)
    except DoesNotExistException:
        return return_json(generate_error('NOTFOUND', 'Person does not exist'))

@APP.route('/api/person/<person>/decks')
@fill_args('season_id')
def person_decks_api(person: str, season_id: int = 0) -> Response:
    p = ps.load_person_by_discord_id_or_username(person, season_id=season_id)
    blob = {
        'name': p.name,
        'decks': p.decks,
    }
    return return_json(blob)

@APP.route('/api/person/<person>/h2h')
@fill_args('season_id')
def person_h2h_api(person: str, season_id: int = 0) -> Response:
    p = ps.load_person_by_discord_id_or_username(person, season_id=season_id)
    return return_json(p.head_to_head)

@APP.route('/api/league/run/<person>')
def league_run_api(person: str) -> Response:
    decks = league.active_decks_by(person)
    if len(decks) == 0:
        return return_json(None)

    run = guarantee_at_most_one_or_retire(decks)
    if run is None:
        return return_json(None)

    decks = league.active_decks()
    already_played = [m.opponent_deck_id for m in match.load_matches_by_deck(run)]
    run.can_play = [d.person for d in decks if d.person != person and d.id not in already_played]

    return return_json(run)

@APP.route('/api/league/drop/<person>', methods=['POST'])
def drop(person: str) -> Response:
    error = validate_api_key()
    if error:
        return error

    decks = league.active_decks_by(person)
    if len(decks) == 0:
        return return_json(generate_error('NO_ACTIVE_RUN', 'That person does not have an active run'))

    run = guarantee.exactly_one(decks)

    league.retire_deck(run)
    result = {'success':True}
    return return_json(result)

@APP.route('/api/rotation')
def rotation_api() -> Response:
    now = dtutil.now()
    diff = rotation.next_rotation() - now
    result = {
        'last': rotation.last_rotation_ex(),
        'next': rotation.next_rotation_ex(),
        'diff': diff.total_seconds(),
        'friendly_diff': dtutil.display_time(diff.total_seconds())
    }
    return return_json(result)

@APP.route('/api/cards')
def cards_api() -> Response:
    blob = {'cards': cs.load_cards()}
    return return_json(blob)

@APP.route('/api/card/<card>')
def card_api(card: str) -> Response:
    return return_json(oracle.load_card(card))

@APP.route('/api/archetype/reassign', methods=['POST'])
@auth.demimod_required
@fill_form('deck_id', 'archetype_id')
def post_reassign(deck_id: int, archetype_id: int) -> Response:
    archs.assign(deck_id, archetype_id)
    redis.clear(f'decksite:deck:{deck_id}')
    return return_json({'success':True, 'deck_id':deck_id})

@APP.route('/api/rule/update', methods=['POST'])
@auth.demimod_required
@fill_form('rule_id')
def post_rule_update(rule_id: int = None) -> Response:
    if rule_id is not None and request.form.get('include') is not None and request.form.get('exclude') is not None:
        inc = []
        exc = []
        for line in cast(str, request.form.get('include')).strip().splitlines():
            try:
                inc.append(parse_line(line))
            except InvalidDataException:
                return return_json({'success':False, 'msg':f"Couldn't find a card count and name on line: {line}"})
            if not cs.card_exists(inc[-1][1]):
                return return_json({'success':False, 'msg':f'Card not found in any deck: {line}'})
        for line in cast(str, request.form.get('exclude')).strip().splitlines():
            try:
                exc.append(parse_line(line))
            except InvalidDataException:
                return return_json({'success':False, 'msg':f"Couldn't find a card count and name on line: {line}"})
            if not cs.card_exists(exc[-1][1]):
                return return_json({'success':False, 'msg':f'Card not found in any deck {line}'})
        rs.update_cards(rule_id, inc, exc)
        return return_json({'success':True})
    return return_json({'success':False, 'msg':'Required keys not found'})

@APP.route('/api/sitemap/')
def sitemap() -> Response:
    urls = [url_for(rule.endpoint) for rule in APP.url_map.iter_rules() if 'GET' in rule.methods and len(rule.arguments) == 0]
    return return_json({'urls': urls})

@APP.route('/api/intro/')
def intro() -> Response:
    return return_json(not request.cookies.get('hide_intro', False) and not auth.hide_intro())

@APP.route('/api/intro/', methods=['POST'])
def hide_intro() -> Response:
    r = Response(response='')
    r.set_cookie('hide_intro', value=str(True), expires=dtutil.dt2ts(dtutil.now()) + 60 *  60 * 24 * 365 * 10)
    return r

@APP.route('/api/status/')
@auth.load_person
def person_status() -> Response:
    username = auth.mtgo_username()
    r = {
        'mtgo_username': username,
        'discord_id': auth.discord_id(),
        'admin': session.get('admin', False),
        'demimod': session.get('demimod', False),
        'hide_intro': request.cookies.get('hide_intro', False) or auth.hide_intro() or username or auth.discord_id(),
        'in_guild': session.get('in_guild', False),
        }
    if username:
        d = guarantee_at_most_one_or_retire(league.active_decks_by(username))
        if d is not None:
            r['deck'] = {'name': d.name, 'url': url_for('deck', deck_id=d.id), 'wins': d.get('wins', 0), 'losses': d.get('losses', 0)} # type: ignore
    if r['admin'] or r['demimod']:
        r['archetypes_to_tag'] = len(deck.load_decks('NOT d.reviewed'))
    active_league = league.active_league()
    if active_league:
        time_until_league_end = active_league.end_date - datetime.datetime.now(tz=datetime.timezone.utc)
        if time_until_league_end <= datetime.timedelta(days=2):
            r['league_end'] = dtutil.display_time(time_until_league_end/datetime.timedelta(seconds=1), granularity=2)
    return return_json(r)

def guarantee_at_most_one_or_retire(decks: List[Deck]) -> Optional[Deck]:
    try:
        run = guarantee.at_most_one(decks)
    except TooManyItemsException:
        league.retire_deck(decks[0])
        run = decks[1]
    return run

@APP.route('/api/admin/people/<int:person_id>/notes/')
@auth.admin_required_no_redirect
def person_notes(person_id: int) -> Response:
    return return_json({'notes': ps.load_notes(person_id)})

@APP.route('/decks/<int:deck_id>/oembed')
def deck_embed(deck_id: int) -> Response:
    # Discord doesn't actually show this yet.  I've reached out to them for better documentation about what they do/don't accept.
    d = deck.load_deck(deck_id)
    view = DeckEmbed(d, None, None)
    width = 1200
    height = 500
    embed = {
        'type': 'rich',
        'version': '1.0',
        'title': view.page_title(),
        'width': width,
        'height': height,
        'html': template.render(view)
    }
    return return_json(embed)

@APP.route('/api/test_500')
def test_500() -> Response:
    if configuration.get_bool('production'):
        return return_json(generate_error('ON_PROD', 'This only works on test environments'), status=404)
    raise TooManyItemsException()

@APP.route('/api/achievements')
def all_achievements() -> Response:
    data = {}
    data['achievements'] = [{'key': a.key, 'title': a.title, 'description': a.description_safe} for a in Achievement.all_achievements]
    return return_json(data)
