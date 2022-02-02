import datetime
import json
import sys
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, cast

from flask import Response, request, session, url_for
from flask_restx import Resource, fields

from decksite import APP, auth, league
from decksite.data import archetype as archs
from decksite.data import card
from decksite.data import competition as comp
from decksite.data import deck, match
from decksite.data import person as ps
from decksite.data import playability, query
from decksite.data import rule as rs
from decksite.data.achievements import Achievement
from decksite.prepare import (prepare_cards, prepare_decks, prepare_leaderboard, prepare_matches,
                              prepare_people)
from decksite.views import DeckEmbed
from find import search as card_search
from magic import oracle, rotation, seasons, tournaments
from magic.models import Deck
from shared import configuration, dtutil, guarantee
from shared import redis_wrapper as redis
from shared.pd_exception import (DoesNotExistException, InvalidArgumentException,
                                 TooManyItemsException)
from shared_web import template
from shared_web.api import generate_error, return_camelized_json, return_json, validate_api_key
from shared_web.decorators import fill_args, fill_form

# pylint: disable=no-self-use

SearchItem = Dict[str, str]

DEFAULT_LIVE_TABLE_PAGE_SIZE = 20
SEARCH_CACHE: List[SearchItem] = []

DECK_ENTRY = APP.api.model('DecklistEntry', {
    'n': fields.Integer(),
    'name': fields.String(),
})

DECK = APP.api.model('Deck', {
    'id': fields.Integer(readonly=True),
    'name': fields.String(),
    'created_date': fields.DateTime(),
    'updated_date': fields.DateTime(),
    'wins': fields.Integer(),
    'losses': fields.Integer(),
    'draws': fields.Integer(),
    'finish': fields.Integer(),
    'archetype_id': fields.Integer(),
    'archetype_name': fields.String(),
    'source_url': fields.String(),
    'competition_id': fields.Integer(),
    'competition_name': fields.String(),
    'person': fields.String(),
    'decklist_hash': fields.String(),
    'retired': fields.Boolean(),
    'colors': fields.List(fields.String()),
    'omw': fields.String(),
    'season_id': fields.Integer(),
    'maindeck': fields.List(fields.Nested(DECK_ENTRY)),
    'sideboard': fields.List(fields.Nested(DECK_ENTRY)),
    'url': fields.String(),
    'source_name': fields.String(),
    'competition_type_name': fields.String(),
    'last_archetype_change': fields.Integer(),
})

COMPETITION = APP.api.model('Competition', {
    'id': fields.Integer(readonly=True),
    'name': fields.String(),
    'start_date': fields.DateTime(),
    'end_date': fields.DateTime(),
    # 'url': fields.Url('competition'),
    'top_n': fields.Integer(),
    'num_decks': fields.Integer(),
    'num_reviewed': fields.Integer(),
    'sponsor_name': fields.String(),
    'series_name': fields.String(),
    'type': fields.String(),
    'season_id': fields.Integer(),
    'decks': fields.List(fields.Nested(DECK)),
})

DECKS = APP.api.model('MultipleDecks', {
    'objects': fields.List(fields.Nested(DECK)),
    'page': fields.Integer(),
    'total': fields.Integer(),
})

RELEASE_DATE = APP.api.model('ReleaseDate', {
    'exact': fields.DateTime(),
    'rough': fields.String(),
})

SET = APP.api.model('Set', {
    'code': fields.String(),
    'name': fields.String(),
    'enter_date': fields.Nested(RELEASE_DATE),
    'exit_date': fields.Nested(RELEASE_DATE),
    'enter_date_dt': fields.String(),
})

ROTATION_DETAILS = APP.api.model('RotationDetails', {
    'last': fields.Nested(SET),
    'next': fields.Nested(SET),
    'diff': fields.Float(),
    'friendly_diff': fields.String(),
})

@APP.route('/api/decks/')
def decks_api() -> Response:
    """
    Grab a slice of results from a 0-indexed resultset of decks.
    Input:
        {
            'archetypeId': <int?>,
            'cardName': <str?>,
            'competitionId': <int?>,
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
            'objects': [<deck>],
            'total': <int>
        }
    """
    order_by = query.decks_order_by(request.args.get('sortBy'), request.args.get('sortOrder'), request.args.get('competitionId'))
    page_size = int(request.args.get('pageSize', DEFAULT_LIVE_TABLE_PAGE_SIZE))
    page = int(request.args.get('page', 0))
    start = page * page_size
    limit = f'LIMIT {start}, {page_size}'
    # Don't restrict by season if we're loading something with a date by its id.
    season_id = 'all' if request.args.get('competitionId') else seasons.season_id(str(request.args.get('seasonId')), None)
    where = query.decks_where(request.args, cast(bool, session.get('admin')), cast(int, session.get('person_id')))
    total = deck.load_decks_count(where=where, season_id=season_id)
    ds = deck.load_decks(where=where, order_by=order_by, limit=limit, season_id=season_id)
    prepare_decks(ds)
    r = {'page': page, 'total': total, 'objects': ds}
    resp = return_camelized_json(r)
    resp.set_cookie('page_size', str(page_size))
    return resp

@APP.api.route('/decks/updated/')
class UpdatedDecks(Resource):
    @APP.api.marshal_with(DECKS)
    def get(self) -> Dict[str, Any]:
        """
        Grab a slice of finished sorted decks last updated after a certain point.
        Input:
            {
                'sortBy': <str>,
                'sortOrder': <'ASC'|'DESC'>,
                'page': <int>,
                'pageSize': <int>,
                'since': <int>,
                'seasonId': <int|'all'>
            }
        Output:
            {
                'page': <int>,
                'objects': [<deck>],
                'total: <int>
            }
        """
        season = seasons.season_id(str(request.args.get('seasonId')), None)
        page_size = int(request.args.get('pageSize', DEFAULT_LIVE_TABLE_PAGE_SIZE))
        page = int(request.args.get('page', 0))
        timestamp = int(request.args.get('since', 0))
        if timestamp < 1e9:
            raise InvalidArgumentException('Invalid timestamp!')
        start = page * page_size
        limit = f'LIMIT {start}, {page_size}'
        where = '(' + query.decks_where(request.args, False, None) + ') AND ' + query.decks_updated_since(timestamp)
        total = deck.load_decks_count(where=where, season_id=season)
        ds = deck.load_decks(where=where, order_by='d.id DESC', limit=limit, season_id=season)
        prepare_decks(ds)
        return {'page': page, 'total': total, 'objects': ds}

@APP.route('/api/cards2/')
def cards2_api() -> Response:
    """
    Grab a slice of results from a 0-indexed resultset of cards.
    Input:
        {
            'deckType': <'league'|'tournament'|'all'>,
            'page': <int>,
            'pageSize': <int>,
            'personId': <int?>,
            'sortBy': <str>,
            'sortOrder': <'ASC'|'DESC'>,
            'seasonId': <int|'all'>,
            'q': <str>
        }
    Output:
        {
            'page': <int>,
            'objects': [<card>],
            'total': <int>
        }
    """
    order_by = query.cards_order_by(request.args.get('sortBy'), request.args.get('sortOrder'))
    page_size = int(request.args.get('pageSize', DEFAULT_LIVE_TABLE_PAGE_SIZE))
    page = int(request.args.get('page', 0))
    start = page * page_size
    limit = f'LIMIT {start}, {page_size}'
    person_id = request.args.get('personId') or None
    tournament_only = request.args.get('deckType') == 'tournament'
    season_id = seasons.season_id(str(request.args.get('seasonId')), None)
    q = request.args.get('q', '').strip()
    additional_where = query.card_search_where(q) if q else 'TRUE'
    cs = card.load_cards(additional_where=additional_where, order_by=order_by, limit=limit, person_id=person_id, tournament_only=tournament_only, season_id=season_id)
    prepare_cards(cs, tournament_only=tournament_only)
    total = card.load_cards_count(additional_where=additional_where, person_id=person_id, season_id=season_id)
    r = {'page': page, 'total': total, 'objects': cs}
    resp = return_camelized_json(r)
    resp.set_cookie('page_size', str(page_size))
    return resp

@APP.route('/api/people/')
def people_api() -> Response:
    """
    Grab a slice of results from a 0-indexed resultset of people.
    Input:
        {
            'page': <int>,
            'pageSize': <int>,
            'sortBy': <str>,
            'sortOrder': <'ASC'|'DESC'>,
            'seasonId': <int|'all'>,
            'q': <str>
        }
    Output:
        {
            'page': <int>,
            'objects': [<person>],
            'total': <int>
        }
    """
    order_by = query.people_order_by(request.args.get('sortBy'), request.args.get('sortOrder'))
    page_size = int(request.args.get('pageSize', DEFAULT_LIVE_TABLE_PAGE_SIZE))
    page = int(request.args.get('page', 0))
    start = page * page_size
    limit = f'LIMIT {start}, {page_size}'
    season_id = seasons.season_id(str(request.args.get('seasonId')), None)
    q = request.args.get('q', '').strip()
    where = query.text_match_where(query.person_query(), q) if q else 'TRUE'
    people = ps.load_people(where=where, order_by=order_by, limit=limit, season_id=season_id)
    prepare_people(people)
    total = ps.load_people_count(where=where, season_id=season_id)
    r = {'page': page, 'total': total, 'objects': people}
    resp = return_camelized_json(r)
    resp.set_cookie('page_size', str(page_size))
    return resp

@APP.route('/api/h2h/')
def h2h_api() -> Response:
    """
    Grab a slice of results from a 0-indexed resultset of head-to-head entries.
    Input:
        {
            'page': <int>,
            'pageSize': <int>,
            'personId': <int>,
            'sortBy': <str>,
            'sortOrder': <'ASC'|'DESC'>,
            'seasonId': <int|'all'>,
            'q': <str>
        }
    Output:
        {
            'page': <int>,
            'objects': [<entry>],
            'total': <int>
        }
    """
    order_by = query.head_to_head_order_by(request.args.get('sortBy'), request.args.get('sortOrder'))
    page_size = int(request.args.get('pageSize', DEFAULT_LIVE_TABLE_PAGE_SIZE))
    page = int(request.args.get('page', 0))
    start = page * page_size
    limit = f'LIMIT {start}, {page_size}'
    season_id = seasons.season_id(str(request.args.get('seasonId')), None)
    person_id = int(request.args.get('personId', 0))
    q = request.args.get('q', '').strip()
    where = query.text_match_where('opp.mtgo_username', q) if q else 'TRUE'
    entries = ps.load_head_to_head(person_id, where=where, order_by=order_by, limit=limit, season_id=season_id)
    for entry in entries:
        entry.opp_url = url_for('seasons.person', mtgo_username=entry.opp_mtgo_username, season_id=season_id)
    total = ps.load_head_to_head_count(person_id=person_id, where=where, season_id=season_id)
    r = {'page': page, 'total': total, 'objects': entries}
    resp = return_camelized_json(r)
    resp.set_cookie('page_size', str(page_size))
    return resp

@APP.route('/api/leaderboards/')
def leaderboards_api() -> Response:
    """
    Grab a slice of results from a 0-indexed resultset of leaderboard entries.
    Input:
        {
            'competitionId': <int?>,
            'competitionSeriesId': <int?>
            'page': <int>,
            'pageSize': <int>,
            'sortBy': <str>,
            'sortOrder': <'ASC'|'DESC'>,
            'seasonId': <int|'all'?>,
            'q': <str>
        }
    Output:
        {
            'page': <int>,
            'objects': [<entry>],
            'total': <int>
        }
    """
    order_by = query.leaderboard_order_by(request.args.get('sortBy'), request.args.get('sortOrder'))
    page_size = int(request.args.get('pageSize', DEFAULT_LIVE_TABLE_PAGE_SIZE))
    page = int(request.args.get('page', 0))
    start = page * page_size
    limit = f'LIMIT {start}, {page_size}'

    q = request.args.get('q', '').strip()
    where = query.text_match_where(query.person_query(), q) if q else 'TRUE'
    try:
        competition_id = int(request.args.get('competitionId', ''))
        where += f' AND (c.id = {competition_id})'
        season_id = None
    except ValueError:
        season_id = seasons.season_id(str(request.args.get('seasonId')), None)
    try:
        competition_series_id = int(request.args.get('competitionSeriesId', ''))
        where += f' AND (cs.id = {competition_series_id})'
    except ValueError:
        pass
    entries = comp.load_leaderboard(where=where, group_by='p.id', order_by=order_by, limit=limit, season_id=season_id)
    prepare_leaderboard(entries)
    total = comp.load_leaderboard_count(where=where, season_id=season_id)
    r = {'page': page, 'total': total, 'objects': entries}
    resp = return_camelized_json(r)
    resp.set_cookie('page_size', str(page_size))
    return resp

@APP.route('/api/matches/')
def matches_api() -> Response:
    """
    Grab a slice of results from a 0-indexed resultset of matches.
    Input:
        {
            'competitionId': <int?>,
            'page': <int>,
            'pageSize': <int>,
            'q': <str>,
            'sortBy': <str>,
            'sortOrder': <'ASC'|'DESC'>,
            'seasonId': <int|'all'?>
        }
    Output:
        {
            'page': <int>,
            'objects': [<entry>],
            'total': <int>
        }
    """
    order_by = query.matches_order_by(request.args.get('sortBy'), request.args.get('sortOrder'))
    page_size = int(request.args.get('pageSize', DEFAULT_LIVE_TABLE_PAGE_SIZE))
    page = int(request.args.get('page', 0))
    start = page * page_size
    limit = f'LIMIT {start}, {page_size}'
    q = request.args.get('q', '').strip()
    person_where = query.text_match_where(query.person_query(), q) if q else 'TRUE'
    opponent_where = query.text_match_where(query.person_query('o'), q) if q else 'TRUE'
    where = f'({person_where} OR {opponent_where})'
    try:
        competition_id = int(request.args.get('competitionId', ''))
        where += f' AND (c.id = {competition_id})'
        season_id = None
    except ValueError:
        season_id = seasons.season_id(str(request.args.get('seasonId')), None)
    entries = match.load_matches(where=where, order_by=order_by, limit=limit, season_id=season_id, show_active_deck_names=session.get('admin', False))
    prepare_matches(entries)
    total = match.load_matches_count(where=where, season_id=season_id)
    r = {'page': page, 'total': total, 'objects': entries}
    resp = return_camelized_json(r)
    resp.set_cookie('page_size', str(page_size))
    return resp

@APP.route('/api/archetypes/')
def archetypes_api() -> Response:
    """
    Grabs the archetype tree.
    Input: nothing
    Output:
        {
            total: int,
            objects: [
                { name: str, parent: str }
            ]
        }
    """
    data = archs.load_archetype_tree()
    r = {'total': len(data), 'objects': data}
    return return_camelized_json(r)

@APP.route('/api/rotation/cards/')
def rotation_cards_api() -> Response:
    """
    Grab a slice of results from a 0-indexed resultset of cards that are potentially rotating in.
    Input:
        {
            'page': <int>,
            'pageSize': <int>,
            'q': <str>,
            'sortBy': <str>,
            'sortOrder': <'ASC'|'DESC'>
        }
    Output:
        {
            'page': <int>,
            'objects': [<entry>],
            'total': <int>
        }
    """
    _, _, cs = rotation.read_rotation_files()
    q = request.args.get('q', '').lower()
    search_results = None
    try:
        search_results = [c.name for c in card_search.search(q)] if q else None
    except card_search.InvalidSearchException:
        pass
    if search_results is not None:
        cs = [c for c in cs if c.name in search_results]
    if not session.get('admin', False):
        cs = [c for c in cs if c.status != 'Undecided']
    # Now add rank to the cards, which only decksite knows not magic.rotation.
    ranks = playability.rank()
    for c in cs:
        c.rank = ranks.get(c.name, 0 if c.never_legal() else sys.maxsize)
        if c.rank == 0:
            c.display_rank = 'NEW'
        elif c.rank == sys.maxsize:
            c.display_rank = '-'
        else:
            c.display_rank = str(c.rank)
    rotation.rotation_sort(cs, request.args.get('sortBy'), request.args.get('sortOrder'))
    total = len(cs)
    page_size = int(request.args.get('pageSize', DEFAULT_LIVE_TABLE_PAGE_SIZE))
    page = int(request.args.get('page', 0))
    start = page * page_size
    end = start + page_size
    cs = cs[start:end]
    prepare_cards(cs)
    r = {'page': page, 'total': total, 'objects': cs}
    resp = return_camelized_json(r)
    resp.set_cookie('page_size', str(page_size))
    return resp

@APP.api.route('/decks/<int:deck_id>')
class LoadDeck(Resource):
    @APP.api.marshal_with(DECK)
    def get(self, deck_id: int) -> Deck:
        return deck.load_deck(deck_id)

@APP.api.route('/randomlegaldeck')
class LoadRandomDeck(Resource):
    @APP.api.marshal_with(DECK)
    def get(self) -> Optional[Deck]:
        blob = league.random_legal_deck()
        if blob is None:
            APP.api.abort(404, 'No legal decks could be found')
            return None
        blob['url'] = url_for('deck', deck_id=blob['id'], _external=True)
        return blob

@APP.api.route('/rotation')
class Rotation(Resource):
    @APP.api.marshal_with(ROTATION_DETAILS)
    def get(self) -> Dict[str, Any]:
        now = dtutil.now()
        diff = seasons.next_rotation() - now
        result = {
            'last': seasons.last_rotation_ex(),
            'next': seasons.next_rotation_ex(),
            'diff': diff.total_seconds(),
            'friendly_diff': dtutil.display_time(int(diff.total_seconds())),
        }
        return result

@APP.route('/api/competitions')
def competitions_api() -> Response:
    # Don't send competitions with any decks that do not have their correct archetype to third parties otherwise they
    # will store it and be wrong forever.
    comps = comp.load_competitions(having='num_reviewed = num_decks', limit='LIMIT 50', should_load_decks=True)
    r = []
    for c in comps:
        if c.decks:
            cr = {}
            cr['id'] = c.id
            cr['name'] = c.name
            cr['url'] = url_for('competition_api', competition_id=c.id, _external=True)
            r.append(cr)
    return return_json(r)

@APP.route('/api/competitions/<competition_id>')
def competition_api(competition_id: int) -> Response:
    return return_json(comp.load_competition(competition_id))

@APP.api.route('/league')
class League(Resource):
    @APP.api.marshal_with(COMPETITION)
    def get(self) -> comp.Competition:
        lg = league.active_league(should_load_decks=True)
        pdbot = request.form.get('api_token', None) == configuration.get('pdbot_api_token')
        if not pdbot:
            lg.decks = [d for d in lg.decks if not d.is_in_current_run()]
        return lg

@APP.api.route('/seasoncodes')
class SeasonCodes(Resource):
    def get(self) -> List[str]:
        return seasons.SEASONS[:seasons.current_season_num()]

@APP.route('/api/person/<person>')
@fill_args('season_id')
def person_api(person: str, season_id: int = -1) -> Response:
    if season_id == -1:
        season_id = seasons.current_season_num()
    try:
        p = ps.load_person_by_discord_id_or_username(person, season_id)
        p.decks_url = url_for('person_decks_api', person=person, season_id=season_id)
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
    result = {'success': True}
    return return_json(result)

@APP.route('/api/rotation/clear_cache')
def rotation_clear_cache() -> Response:
    rotation.clear_redis()
    rotation.rotation_redis_store()
    return return_json({'success': True})

@APP.route('/api/cards')
def cards_api() -> Response:
    blob = {'cards': card.load_cards()}
    return return_json(blob)

@APP.route('/api/card/<card>')
def card_api(c: str) -> Response:
    return return_json(oracle.load_card(c))

@APP.route('/api/archetype/reassign', methods=['POST'])
@auth.demimod_required
@fill_form('deck_id', 'archetype_id')
def post_reassign(deck_id: int, archetype_id: int) -> Response:
    archs.assign(deck_id, archetype_id, auth.person_id())
    redis.clear(f'decksite:deck:{deck_id}')
    return return_json({'success': True, 'deck_id': deck_id})

@APP.route('/api/rule/update', methods=['POST'])
@fill_form('rule_id')
@auth.demimod_required
def post_rule_update(rule_id: int = None) -> Response:
    if rule_id is not None and request.form.get('include') is not None and request.form.get('exclude') is not None:
        success, msg = rs.update_cards_raw(rule_id, request.form.get('include', ''), request.form.get('exclude', ''))
        return return_json({'success': success, 'msg': msg})
    return return_json({'success': False, 'msg': 'Required keys not found'})

@APP.route('/api/sitemap/')
def sitemap() -> Response:
    urls = [url_for(rule.endpoint) for rule in APP.url_map.iter_rules() if rule.methods and 'GET' in rule.methods and len(rule.arguments) == 0]
    return return_json({'urls': urls})

@APP.route('/api/intro/')
def intro() -> Response:
    return return_json(not request.cookies.get('hide_intro', False) and not auth.hide_intro())

@APP.route('/api/intro/', methods=['POST'])
def hide_intro() -> Response:
    r = Response(response='')
    r.set_cookie('hide_intro', value=str(True), expires=dtutil.dt2ts(dtutil.now()) + 60 * 60 * 24 * 365 * 10)
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
            r['deck'] = {'name': d.name, 'url': url_for('deck', deck_id=d.id), 'wins': d.get('wins', 0), 'losses': d.get('losses', 0)}
    if r['admin'] or r['demimod']:
        r['archetypes_to_tag'] = len(deck.load_decks('NOT d.reviewed'))
    active_league = league.active_league()
    if active_league:
        time_until_league_end = active_league.end_date - datetime.datetime.now(tz=datetime.timezone.utc)
        if time_until_league_end <= datetime.timedelta(days=2):
            r['league_end'] = dtutil.display_time(time_until_league_end / datetime.timedelta(seconds=1), granularity=2)
    return return_json(r)

def guarantee_at_most_one_or_retire(decks: List[Deck]) -> Optional[Deck]:
    try:
        run = guarantee.at_most_one(decks)
    except TooManyItemsException:
        league.retire_deck(decks[0])
        run = decks[1]
    return run

@APP.route('/api/key_cards/<int:season_num>')
def key_cards(season_num: int) -> Response:
    data = playability.key_cards(season_num)
    return return_json({'data': data})


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
        'html': template.render(view),
    }
    return return_json(embed)

@APP.route('/api/test_500')
def trigger_test_500() -> Response:
    if configuration.production.value:
        return return_json(generate_error('ON_PROD', 'This only works on test environments'), status=404)
    raise TooManyItemsException

@APP.route('/api/achievements')
def all_achievements() -> Response:
    data = {}
    data['achievements'] = [{'key': a.key, 'title': a.title, 'description': a.description_safe} for a in Achievement.all_achievements]
    return return_json(data)

@APP.route('/api/tournaments')
def all_tournaments() -> Response:
    data = {}
    data['tournaments'] = (tournaments.all_series_info())
    return return_json(data)

@APP.route('/api/search/')
def search() -> Response:
    init_search_cache()
    q = request.args.get('q', '').lower()
    results: List[SearchItem] = []
    if len(q) < 2:
        return return_json(results)
    for item in SEARCH_CACHE:
        if q in item['name'].lower():
            results.append(item)
    return return_json(results)

def init_search_cache() -> None:
    if len(SEARCH_CACHE) > 0:
        return
    submenu_entries = []  # Accumulate the submenu entries and add them after the top-level entries as they are less important.
    for entry in APP.config.get('menu', lambda: [])():
        if entry.get('admin_only'):
            continue
        SEARCH_CACHE.append(menu_item_to_search_item(entry))
        for subentry in entry.get('submenu', []):
            submenu_entries.append(menu_item_to_search_item(subentry, entry.get('name')))
    for entry in submenu_entries:
        if entry.get('admin_only'):
            continue
        SEARCH_CACHE.append(menu_item_to_search_item(entry))
    with open(configuration.get_str('typeahead_data_path')) as f:
        for item in json.load(f):
            SEARCH_CACHE.append(item)

def menu_item_to_search_item(menu_item: Dict[str, Any], parent_name: Optional[str] = None) -> Dict[str, Any]:
    name = ''
    if parent_name:
        name += f'{parent_name} – '
    name += menu_item.get('name', '')
    if menu_item.get('url'):
        url = menu_item.get('url')
    else:
        url = url_for(menu_item.get('endpoint', ''))
    return {'name': name, 'type': 'Page', 'url': url}
