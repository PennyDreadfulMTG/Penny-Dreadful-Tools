import urllib.parse
from typing import List, Optional

from flask import redirect, request, url_for
from werkzeug import wrappers

from decksite import APP, SEASONS, auth, get_season_id
from decksite.cache import cached
from decksite.data import archetype as archs
from decksite.data import card as cs
from decksite.data import deck as ds
from decksite.data import matchup as mus
from decksite.data import person as ps
from decksite.data import season as ss
from decksite.deck_type import DeckType
from decksite.views import Archetype, Archetypes, Card, Cards, Deck, Decks, Matchups, Seasons
from magic import oracle
from shared.pd_exception import DoesNotExistException, InvalidDataException


@APP.route('/decks/')
@APP.route('/decks/<any(tournament,league):deck_type>/')
@SEASONS.route('/decks/')
@SEASONS.route('/decks/<any(tournament,league):deck_type>/')
@cached()
def decks(deck_type: Optional[str] = None) -> str:
    league_only = validate_deck_type(deck_type, [DeckType.ALL, DeckType.LEAGUE]) == DeckType.LEAGUE
    view = Decks(league_only)
    return view.page()

@APP.route('/decks/<int:deck_id>/')
@auth.load_person
def deck(deck_id: int) -> str:
    d = ds.load_deck(deck_id)
    view = Deck(d, auth.person_id(), auth.discord_id())
    return view.page()

@APP.route('/seasons/')
@cached()
def seasons() -> str:
    stats = ss.season_stats()
    view = Seasons(stats)
    return view.page()

@SEASONS.route('/')
@cached()
def season() -> wrappers.Response:
    return redirect(url_for('seasons.decks'))

@APP.route('/cards/')
@APP.route('/cards/<any(tournament,league):deck_type>/')
@SEASONS.route('/cards/')
@SEASONS.route('/cards/<any(tournament,league):deck_type>/')
@cached()
def cards(deck_type: Optional[str] = None) -> str:
    tournament_only = validate_deck_type(deck_type, [DeckType.ALL, DeckType.TOURNAMENT]) == DeckType.TOURNAMENT
    query = request.args.get('fq')
    if query is None:
        query = ''
    all_cards = cs.load_cards(season_id=get_season_id(), tournament_only=tournament_only)
    view = Cards(all_cards, query=query, tournament_only=tournament_only)
    return view.page()

@APP.route('/cards/<path:name>/')
@APP.route('/cards/<path:name>/<any(tournament,league):deck_type>/')
@SEASONS.route('/cards/<path:name>/')
@SEASONS.route('/cards/<path:name>/<any(tournament,league):deck_type>/')
@cached()
def card(name: str, deck_type: Optional[str] = None) -> str:
    tournament_only = validate_deck_type(deck_type, [DeckType.ALL, DeckType.TOURNAMENT]) == DeckType.TOURNAMENT
    try:
        c = cs.load_card(oracle.valid_name(urllib.parse.unquote_plus(name)), tournament_only=tournament_only, season_id=get_season_id())
        view = Card(c, tournament_only)
        return view.page()
    except InvalidDataException as e:
        raise DoesNotExistException(e) from e


@APP.route('/archetypes/')
@APP.route('/archetypes/<any(tournament,league):deck_type>/')
@SEASONS.route('/archetypes/')
@SEASONS.route('/archetypes/<any(tournament,league):deck_type>/')
@cached()
def archetypes(deck_type: Optional[str] = None) -> str:
    tournament_only = validate_deck_type(deck_type, [DeckType.ALL, DeckType.TOURNAMENT]) == DeckType.TOURNAMENT
    season_id = get_season_id()
    deckless_archetypes = archs.load_archetypes_deckless(season_id=season_id, tournament_only=tournament_only)
    all_matchups = archs.load_matchups(season_id=season_id, tournament_only=tournament_only)
    view = Archetypes(deckless_archetypes, all_matchups, tournament_only=tournament_only)
    return view.page()

@APP.route('/archetypes/<archetype_id>/')
@APP.route('/archetypes/<archetype_id>/<any(tournament,league):deck_type>/')
@SEASONS.route('/archetypes/<archetype_id>/')
@SEASONS.route('/archetypes/<archetype_id>/<any(tournament,league):deck_type>/')
@cached()
def archetype(archetype_id: str, deck_type: Optional[str] = None) -> str:
    tournament_only = validate_deck_type(deck_type, [DeckType.ALL, DeckType.TOURNAMENT]) == DeckType.TOURNAMENT
    season_id = get_season_id()
    a = archs.load_archetype(archetype_id.replace('+', ' '), season_id=season_id, tournament_only=tournament_only)
    deckless_archetypes = archs.load_archetypes_deckless_for(a.id, season_id=season_id, tournament_only=tournament_only)
    archetype_matchups = archs.load_matchups(archetype_id=a.id, season_id=season_id, tournament_only=tournament_only)
    view = Archetype(a, deckless_archetypes, archetype_matchups, tournament_only=tournament_only, season_id=season_id)
    return view.page()


@APP.route('/matchups/')
def matchups() -> str:
    hero, enemy = {}, {}
    for k, v in request.args.items():
        if k.startswith('hero_'):
            k = k.replace('hero_', '')
            hero[k] = v
        else:
            k = k.replace('enemy_', '')
            enemy[k] = v
    season_id = request.args.get('season_id')
    results = mus.matchup(hero, enemy, season_id=season_id) if 'hero_person_id' in request.args else {}
    matchup_archetypes = archs.load_archetypes_deckless()
    matchup_archetypes.sort(key=lambda a: a.name)
    matchup_people = list(ps.load_people(where='p.mtgo_username IS NOT NULL'))
    matchup_people.sort(key=lambda p: p.name)
    matchup_cards = cs.load_cards()
    matchup_cards.sort(key=lambda c: c.name)
    view = Matchups(hero, enemy, season_id, matchup_archetypes, matchup_people, matchup_cards, results)
    return view.page()


def validate_deck_type(s: Optional[str], allowed_values: List[DeckType] = None) -> DeckType:
    if not s:
        return DeckType.ALL
    try:
        deck_type = DeckType(s)
        if allowed_values and deck_type not in allowed_values:
            raise DoesNotExistException(
                f'Invalid deck_type for this endpoint: {deck_type}')
    except ValueError as e:
        raise DoesNotExistException(e) from e
    return deck_type
