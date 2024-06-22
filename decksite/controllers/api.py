import datetime
import json
from typing import Any, cast

from flask import Response, request, session, url_for
from flask_restx import Resource, fields
from werkzeug.exceptions import BadRequest

from decksite import APP, auth, league
from decksite.data import archetype as archs
from decksite.data import card, clauses, deck, match, playability, query
from decksite.data import competition as comp
from decksite.data import person as ps
from decksite.data import rotation as rot
from decksite.data import rule as rs
from decksite.data.achievements import Achievement
from decksite.data.clauses import DEFAULT_GRID_PAGE_SIZE, DEFAULT_LIVE_TABLE_PAGE_SIZE
from decksite.prepare import colors_html, prepare_archetypes, prepare_cards, prepare_decks, prepare_leaderboard, prepare_matches, prepare_people
from decksite.views import DeckEmbed
from magic import image_fetcher, layout, oracle, rotation, seasons, tournaments
from magic.colors import find_colors
from magic.models import Card, Deck
from shared import configuration, dtutil, guarantee
from shared import redis_wrapper as redis
from shared.container import Container
from shared.pd_exception import DoesNotExistException, InvalidArgumentException, TooManyItemsException
from shared_web import template
from shared_web.api import generate_error, return_camelized_json, return_json, validate_api_key
from shared_web.decorators import fill_args, fill_form
from shared_web.menu import MenuItem

SearchItem = dict[str, str]

SEARCH_CACHE: list[SearchItem] = []

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

@APP.route('/api/decks')
@APP.route('/api/decks/')
def decks_api() -> Response:
    """
    Grab a slice of results from a 0-indexed resultset of decks.
    Input:
        {
            'achievementKey': <str?>,
            'archetypeId': <int?>,
            'cardName': <str?>,
            'competitionId': <int?>,
            'competitionFlagId': <int?>,
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
    order_by = clauses.decks_order_by(request.args.get('sortBy'), request.args.get('sortOrder'), request.args.get('competitionId'))
    page, page_size, limit = pagination(request.args)
    # Don't restrict by season if we're loading something with a date by its id.
    season_id = 'all' if request.args.get('competitionId') else seasons.season_id(str(request.args.get('seasonId')), None)
    where = clauses.decks_where(request.args, cast(bool, session.get('admin')), cast(int, session.get('person_id')))
    ds, total = deck.load_decks(where=where, order_by=order_by, limit=limit, season_id=season_id)
    prepare_decks(ds)
    r = {'page': page, 'total': total, 'objects': ds}
    resp = return_camelized_json(r)
    resp.set_cookie('page_size', str(page_size))
    return resp

@APP.api.route('/decks/updated')
@APP.api.route('/decks/updated/')
class UpdatedDecks(Resource):
    @APP.api.marshal_with(DECKS)
    def get(self) -> dict[str, Any]:
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
        timestamp = int(request.args.get('since', 0))
        if timestamp < 1e9:
            raise InvalidArgumentException('Invalid timestamp!')
        page, page_size, limit = pagination(request.args)
        where = '(' + clauses.decks_where(request.args, False, None) + ') AND ' + clauses.decks_updated_since(timestamp)
        ds, total = deck.load_decks(where=where, order_by='d.id DESC', limit=limit, season_id=season)
        prepare_decks(ds)
        return {'page': page, 'total': total, 'objects': ds}

@APP.route('/api/cards2')
@APP.route('/api/cards2/')
def cards2_api() -> Response:
    """
    Grab a slice of results from a 0-indexed resultset of cards.
    Input:
        {
            'allLegal': <bool>,
            'baseQuery': <str>,
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
            'total': <int>,
            'message': <str>,
        }
    """
    order_by = clauses.cards_order_by(request.args.get('sortBy'), request.args.get('sortOrder'))
    page, page_size, limit = pagination(request.args)
    archetype_id = request.args.get('archetypeId') or None
    person_id = request.args.get('personId') or None
    tournament_only = request.args.get('deckType') == 'tournament'
    season_id = seasons.season_id(str(request.args.get('seasonId')), None)
    base_query = request.args.get('baseQuery')
    q = request.args.get('q', '').strip()
    additional_where, message = clauses.card_search_where(q, base_query, 'cs.name') if q or base_query else ('TRUE', '')
    all_legal = request.args.get('allLegal', False)
    cs, total = card.load_cards(additional_where=additional_where, order_by=order_by, limit=limit, archetype_id=archetype_id, person_id=person_id, tournament_only=tournament_only, season_id=season_id, all_legal=all_legal)
    prepare_cards(cs, tournament_only=tournament_only, season_id=season_id)
    r = {'page': page, 'total': total, 'objects': cs, 'message': message}
    resp = return_camelized_json(r)
    resp.set_cookie('page_size', str(page_size))
    return resp

@APP.route('/api/cardfeed')
@APP.route('/api/cardfeed/')
def cardfeed_api() -> Response:
    """
    A JSON feed of all cards with pd legality and playability rank.
    """
    os = []
    cs = oracle.load_cards()
    ranks = playability.rank()
    for c in cs:
        rank = ranks.get(c.name)
        name = c.name
        # Scryfall requested this naming convention for these layouts even though that is not our standard for them.
        if send_scryfall_two_names(c.layout):
            name = ' // '.join(c.names)
        os.append({'name': name, 'oracle_id': c.oracle_id, 'rank': rank, 'legal': bool(c.pd_legal)})
    r = {'cards': os}
    return return_camelized_json(r)

@APP.route('/api/people')
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
    order_by = clauses.people_order_by(request.args.get('sortBy'), request.args.get('sortOrder'))
    page, page_size, limit = pagination(request.args)
    season_id = seasons.season_id(str(request.args.get('seasonId')), None)
    q = request.args.get('q', '').strip()
    where = clauses.text_where(query.person_query(), q) if q else 'TRUE'
    people, total = ps.load_people(where=where, order_by=order_by, limit=limit, season_id=season_id)
    prepare_people(people)
    r = {'page': page, 'total': total, 'objects': people}
    resp = return_camelized_json(r)
    resp.set_cookie('page_size', str(page_size))
    return resp

@APP.route('/api/h2h')
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
    order_by = clauses.head_to_head_order_by(request.args.get('sortBy'), request.args.get('sortOrder'))
    page, page_size, limit = pagination(request.args)
    season_id = seasons.season_id(str(request.args.get('seasonId')), None)
    person_id = int(request.args.get('personId', 0))
    q = request.args.get('q', '').strip()
    where = clauses.text_match_where('opp.mtgo_username', q) if q else 'TRUE'
    entries, total = ps.load_head_to_head(person_id, where=where, order_by=order_by, limit=limit, season_id=season_id)
    for entry in entries:
        entry.opp_url = url_for('seasons.person', mtgo_username=entry.opp_mtgo_username, season_id=season_id)
    r = {'page': page, 'total': total, 'objects': entries}
    resp = return_camelized_json(r)
    resp.set_cookie('page_size', str(page_size))
    return resp

@APP.route('/api/leaderboards')
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
    order_by = clauses.leaderboard_order_by(request.args.get('sortBy'), request.args.get('sortOrder'))
    page, page_size, limit = pagination(request.args)
    q = request.args.get('q', '').strip()
    where = clauses.text_match_where(query.person_query(), q) if q else 'TRUE'
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
    entries, total = comp.load_leaderboard(where=where, group_by='p.id', order_by=order_by, limit=limit, season_id=season_id)
    prepare_leaderboard(entries)
    r = {'page': page, 'total': total, 'objects': entries}
    resp = return_camelized_json(r)
    resp.set_cookie('page_size', str(page_size))
    return resp

@APP.route('/api/matches')
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
    order_by = clauses.matches_order_by(request.args.get('sortBy'), request.args.get('sortOrder'))
    page, page_size, limit = pagination(request.args)
    q = request.args.get('q', '').strip()
    person_where = clauses.text_match_where(query.person_query(), q) if q else 'TRUE'
    opponent_where = clauses.text_match_where(query.person_query('o'), q) if q else 'TRUE'
    where = f'({person_where} OR {opponent_where})'
    try:
        competition_id = int(request.args.get('competitionId', ''))
        where += f' AND (c.id = {competition_id})'
        season_id = None
    except ValueError:
        season_id = seasons.season_id(str(request.args.get('seasonId')), None)
    entries, total = match.load_matches(where=where, order_by=order_by, limit=limit, season_id=season_id, show_active_deck_names=session.get('admin', False))
    prepare_matches(entries)
    r = {'page': page, 'total': total, 'objects': entries}
    resp = return_camelized_json(r)
    resp.set_cookie('page_size', str(page_size))
    return resp

@APP.route('/api/archetypes')
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

@APP.route('/api/archetypes2')
@APP.route('/api/archetypes2/')
def archetypes2_api() -> Response:
    """
    Grab a slice of results from a 0-indexed resultset of archetypes.

    Input:
        {
            'page': <int>,
            'pageSize': <int>,
            'q': <str?>,
            'seasonId': <int|'all'?>
        }
    Output:
        {
            'page': <int>,
            'objects': [<entry>],
            'total': <int>
        }

    """
    q = request.args.get('q', '').lower()
    where = clauses.text_where('a.name', q) if q else 'TRUE'
    order_by = clauses.archetype_order_by(request.args.get('sortBy'), request.args.get('sortOrder'))
    page, page_size, limit = pagination(request.args, DEFAULT_GRID_PAGE_SIZE)
    tournament_only = request.args.get('deckType') == 'tournament'
    season_id = seasons.season_id(str(request.args.get('seasonId')), None)
    results, total = archs.load_disjoint_archetypes(where=where, order_by=order_by, limit=limit, season_id=season_id, tournament_only=tournament_only)
    archetype_key_cards = playability.key_cards_long(season_id)
    cards = oracle.cards_by_name()
    for result in results:
        kcs = [cards[name] for name in archetype_key_cards.get(result.id, [])]
        result.key_cards = [c for c in kcs if not is_uninteresting(c)][0:5]
        result.num_matches = (result.wins or 0) + (result.losses or 0) + (result.draws or 0)
        colors, colored_symbols = find_colors(oracle.load_cards(archetype_key_cards.get(result.id, [])))
        result.colors_safe = colors_html(colors, colored_symbols)
        kcs = [Card({'name': c['name'], 'url': image_fetcher.scryfall_image(c, 'art_crop')}) for c in result.key_cards]
        result.key_cards = kcs
    prepare_archetypes(results, None, tournament_only, season_id)
    # Remove infinite loops from the results
    results = [Container({k: v for k, v in result.items() if 'NodeMixin' not in k}) for result in results]
    r = {'page': page, 'total': total, 'objects': results}
    resp = return_camelized_json(r)
    return resp

@APP.route('/api/rotation/cards')
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
    q = request.args.get('q', '').lower()
    page, page_size, limit = pagination(request.args)
    where, message = clauses.card_search_where(q) if q else ('TRUE', '')
    if not session.get('admin', False):
        where += " AND status <> 'Undecided'"
    order_by = clauses.rotation_order_by(request.args.get('sortBy'), request.args.get('sortOrder'))
    cs, total = rot.load_rotation(where=where, order_by=order_by, limit=limit)
    prepare_cards(cs)
    r = {'page': page, 'total': total, 'objects': cs, 'message': message}
    resp = return_camelized_json(r)
    resp.set_cookie('page_size', str(page_size))
    return resp

@APP.api.route('/decks/<int:deck_id>')
@APP.api.route('/decks/<int:deck_id>/')
class LoadDeck(Resource):
    @APP.api.marshal_with(DECK)
    def get(self, deck_id: int) -> Deck:
        return deck.load_deck(deck_id)

@APP.api.route('/randomlegaldeck')
@APP.api.route('/randomlegaldeck/')
class LoadRandomDeck(Resource):
    @APP.api.marshal_with(DECK)
    def get(self) -> Deck | None:
        blob = league.random_legal_deck()
        if blob is None:
            APP.api.abort(404, 'No legal decks could be found')
            return None
        blob['url'] = url_for('deck', deck_id=blob['id'], _external=True)
        return blob

@APP.api.route('/rotation')
@APP.api.route('/rotation/')
class Rotation(Resource):
    @APP.api.marshal_with(ROTATION_DETAILS)
    def get(self) -> dict[str, Any]:
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
@APP.route('/api/competitions/')
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
@APP.route('/api/competitions/<competition_id>/')
def competition_api(competition_id: int) -> Response:
    return return_json(comp.load_competition(competition_id))

@APP.api.route('/league')
@APP.api.route('/league/')
class League(Resource):
    @APP.api.marshal_with(COMPETITION)
    def get(self) -> comp.Competition:
        lg = league.active_league(should_load_decks=True)
        pdbot = request.form.get('api_token', None) == configuration.get('pdbot_api_token')
        if not pdbot:
            lg.decks = [d for d in lg.decks if not d.is_in_current_run()]
        return lg
@APP.api.route('/seasoncodes')
@APP.api.route('/seasoncodes/')
class SeasonCodes(Resource):
    def get(self) -> list[str]:
        return seasons.SEASONS[:seasons.current_season_num()]

@APP.route('/api/person/<person>')
@APP.route('/api/person/<person>/')
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
@APP.route('/api/person/<person>/decks/')
@fill_args('season_id')
def person_decks_api(person: str, season_id: int = 0) -> Response:
    p = ps.load_person_by_discord_id_or_username(person, season_id=season_id)
    blob = {
        'name': p.name,
        'decks': p.decks,
    }
    return return_json(blob)

@APP.route('/api/league/run/<person>')
@APP.route('/api/league/run/<person>/')
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
@APP.route('/api/league/drop/<person>/', methods=['POST'])
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

@APP.route('/api/doorprize', methods=['POST'])
@APP.route('/api/doorprize/', methods=['POST'])
def doorprize() -> Response:
    error = validate_api_key()
    if error:
        return error

    comp.set_doorprize(request.form['event'], request.form['winner'])
    return return_json({'success': True})

@APP.route('/api/rotation/clear_cache')
@APP.route('/api/rotation/clear_cache/')
def rotation_clear_cache() -> Response:
    rotation.clear_redis()
    rotation.rotation_redis_store()
    rot.force_cache_update()
    return return_json({'success': True})

@APP.route('/api/cards')
@APP.route('/api/cards/')
def cards_api() -> Response:
    cs, _ = card.load_cards()
    return return_json({'cards': cs})

@APP.route('/api/card/<card>')
@APP.route('/api/card/<card>/')
def card_api(c: str) -> Response:
    return return_json(oracle.load_card(c))

@APP.route('/api/archetype/reassign', methods=['POST'])
@APP.route('/api/archetype/reassign/', methods=['POST'])
@auth.demimod_required
@fill_form('deck_id', 'archetype_id')
def post_reassign(deck_id: int, archetype_id: int) -> Response:
    archs.assign(deck_id, archetype_id, auth.person_id())
    redis.clear(f'decksite:deck:{deck_id}')
    return return_json({'success': True, 'deck_id': deck_id})

@APP.route('/api/rule/update', methods=['POST'])
@APP.route('/api/rule/update/', methods=['POST'])
@fill_form('rule_id')
@auth.demimod_required
def post_rule_update(rule_id: int | None = None) -> Response:
    if rule_id is not None and request.form.get('include') is not None and request.form.get('exclude') is not None:
        success, msg = rs.update_cards_raw(rule_id, request.form.get('include', ''), request.form.get('exclude', ''))
        return return_json({'success': success, 'msg': msg})
    return return_json({'success': False, 'msg': 'Required keys not found'})

@APP.route('/api/sitemap')
@APP.route('/api/sitemap/')
def sitemap() -> Response:
    urls = [url_for(rule.endpoint) for rule in APP.url_map.iter_rules() if rule.methods and 'GET' in rule.methods and len(rule.arguments) == 0]
    return return_json({'urls': urls})

@APP.route('/api/intro')
@APP.route('/api/intro/')
def intro() -> Response:
    return return_json(not request.cookies.get('hide_intro', False) and not auth.hide_intro())

@APP.route('/api/intro', methods=['POST'])
@APP.route('/api/intro/', methods=['POST'])
def hide_intro() -> Response:
    r = Response(response='')
    r.set_cookie('hide_intro', value=str(True), expires=dtutil.dt2ts(dtutil.now()) + 60 * 60 * 24 * 365 * 10)
    return r

@APP.route('/api/status')
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
        _, total = deck.load_decks('NOT d.reviewed', limit='LIMIT 1')
        r['archetypes_to_tag'] = total
    active_league = league.active_league()
    if active_league:
        time_until_league_end = active_league.end_date - datetime.datetime.now(tz=datetime.timezone.utc)
        if time_until_league_end <= datetime.timedelta(days=2):
            r['league_end'] = dtutil.display_time(time_until_league_end / datetime.timedelta(seconds=1), granularity=2)
    return return_json(r)

def guarantee_at_most_one_or_retire(decks: list[Deck]) -> Deck | None:
    try:
        run = guarantee.at_most_one(decks)
    except TooManyItemsException:
        league.retire_deck(decks[0])
        run = decks[1]
    return run

@APP.route('/api/key_cards/<int:season_num>')
@APP.route('/api/key_cards/<int:season_num>/')
def key_cards(season_num: int) -> Response:
    data = playability.key_cards(season_num)
    return return_json({'data': data})


@APP.route('/api/admin/people/<int:person_id>/notes')
@APP.route('/api/admin/people/<int:person_id>/notes/')
@auth.admin_required_no_redirect
def person_notes(person_id: int) -> Response:
    return return_json({'notes': ps.load_notes(person_id)})

@APP.route('/decks/<int:deck_id>/oembed')
def deck_embed(deck_id: int) -> Response:
    # Discord doesn't actually show this yet.  I've reached out to them for better documentation about what they do/don't accept.
    d = deck.load_deck(deck_id)
    view = DeckEmbed(d, [], None, None, [])
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
@APP.route('/api/test_500/')
def trigger_test_500() -> Response:
    if configuration.production.value:
        return return_json(generate_error('ON_PROD', 'This only works on test environments'), status=404)
    raise TooManyItemsException

@APP.route('/api/achievements')
@APP.route('/api/achievements/')
def all_achievements() -> Response:
    data = {}
    data['achievements'] = [{'key': a.key, 'title': a.title, 'description': a.description_safe} for a in Achievement.all_achievements]
    return return_json(data)

@APP.route('/api/tournaments')
@APP.route('/api/tournaments/')
def all_tournaments() -> Response:
    data = {}
    data['tournaments'] = (tournaments.all_series_info())
    return return_json(data)

@APP.route('/api/search')
@APP.route('/api/search/')
def search() -> Response:
    init_search_cache()
    q = request.args.get('q', '').lower()
    exact_matches: list[SearchItem] = []
    fuzzy_matches: list[SearchItem] = []
    if len(q) < 2:
        return return_json([])
    for item in SEARCH_CACHE:
        name = item['name'].lower()
        if q == name:
            exact_matches.append(item)
        elif q in name:
            fuzzy_matches.append(item)
    return return_json(exact_matches + fuzzy_matches)

def init_search_cache() -> None:
    if len(SEARCH_CACHE) > 0:
        return
    submenu_entries = []  # Accumulate the submenu entries and add them after the top-level entries as they are less important.
    for entry in APP.config.get('menu', lambda: [])():
        if entry.permission_required:
            continue
        SEARCH_CACHE.append(menu_item_to_search_item(entry))
        for subentry in entry.submenu:
            if subentry.permission_required:
                continue
            submenu_entries.append(menu_item_to_search_item(subentry))
    for entry in submenu_entries:
        SEARCH_CACHE.append(entry)
    with open(configuration.get_str('typeahead_data_path')) as f:
        for item in json.load(f):
            SEARCH_CACHE.append(item)

def menu_item_to_search_item(menu_item: MenuItem, parent_name: str | None = None) -> dict[str, Any]:
    name = ''
    if parent_name:
        name += f'{parent_name} – '
    name += menu_item.name
    return {'name': name, 'type': 'Page', 'url': menu_item.url}

def pagination(args: dict[str, str], default_page_size: int = DEFAULT_LIVE_TABLE_PAGE_SIZE) -> tuple[int, int, str]:
    try:
        return clauses.pagination(args, default_page_size)
    except InvalidArgumentException as e:
        raise BadRequest from e

def send_scryfall_two_names(lo: str) -> bool:
    return lo in layout.has_two_names() and lo not in layout.has_meld_back()

def is_uninteresting(c: Card) -> bool:
    is_basic = 'Basic' in c.type_line
    is_dual = '} or {' in c.oracle_text or '}, or {' in c.oracle_text
    return c.is_land() and (is_basic or is_dual)
