import urllib.parse
from typing import Dict, List, Optional

from flask import redirect, request, url_for
from werkzeug import wrappers

from decksite import APP, SEASONS, auth, get_season_id
from decksite.cache import cached
from decksite.data import archetype as archs, card as cs, deck as ds, match, matchup as mus, person as ps, playability, season as ss
from decksite.deck_type import DeckType
from decksite.views import (Archetype, Archetypes, Card, Cards, Deck, Decks, Matchups, Metagame, Seasons)
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

@APP.route('/metagame/')
@APP.route('/metagame/<any(tournament,league):deck_type>/')
@SEASONS.route('/metagame/')
@SEASONS.route('/metagame/<any(tournament,league):deck_type>/')
@cached()
def metagame(deck_type: Optional[str] = None) -> str:
    tournament_only = validate_deck_type(deck_type, [DeckType.ALL, DeckType.TOURNAMENT]) == DeckType.TOURNAMENT
    disjoint_archetypes = archs.load_disjoint_archetypes(season_id=get_season_id(), tournament_only=tournament_only)
    key_cards = playability.key_cards(get_season_id())
    view = Metagame(disjoint_archetypes, tournament_only=tournament_only, key_cards=key_cards)
    return view.page()

@APP.route('/decks/<int:deck_id>/')
@auth.load_person
def deck(deck_id: int) -> str:
    d = ds.load_deck(deck_id)
    ms = match.load_matches_by_deck(d)
    view = Deck(d, ms, auth.person_id(), auth.discord_id())
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
    view = Cards(query=query, tournament_only=tournament_only)
    return view.page()

@APP.route('/cards/<path:name>/')
@APP.route('/cards/<path:name>/<any(tournament,league):deck_type>/')
@SEASONS.route('/cards/<path:name>/')
@SEASONS.route('/cards/<path:name>/<any(tournament,league):deck_type>/')
@cached()
def card(name: str, deck_type: Optional[str] = None) -> str:
    tournament_only = validate_deck_type(deck_type, [DeckType.ALL, DeckType.TOURNAMENT]) == DeckType.TOURNAMENT
    try:
        c = cs.load_card(parse_card_name(name), tournament_only=tournament_only, season_id=get_season_id())
        view = Card(c, tournament_only)
        return view.page()
    except InvalidDataException as e:
        raise DoesNotExistException(e) from e

def parse_card_name(name: str) -> str:
    name = urllib.parse.unquote_plus(name)
    if name.startswith(' '):  # Handle "+2 Mace".
        name = '+' + name.lstrip()
    return oracle.valid_name(name)

@APP.route('/archetypes/')
@APP.route('/archetypes/<any(tournament,league):deck_type>/')
@SEASONS.route('/archetypes/')
@SEASONS.route('/archetypes/<any(tournament,league):deck_type>/')
@cached()
def archetypes(deck_type: Optional[str] = None) -> str:
    tournament_only = validate_deck_type(deck_type, [DeckType.ALL, DeckType.TOURNAMENT]) == DeckType.TOURNAMENT
    season_id = get_season_id()
    all_archetypes = archs.load_archetypes(season_id=season_id, tournament_only=tournament_only)
    view = Archetypes(all_archetypes, tournament_only=tournament_only)
    return view.page()

@APP.route('/archetypes/<archetype_id>/')
@APP.route('/archetypes/<archetype_id>/<any(tournament,league):deck_type>/')
@SEASONS.route('/archetypes/<archetype_id>/')
@SEASONS.route('/archetypes/<archetype_id>/<any(tournament,league):deck_type>/')
@cached()
def archetype(archetype_id: str, deck_type: Optional[str] = None) -> str:
    tournament_only = validate_deck_type(deck_type, [DeckType.ALL, DeckType.TOURNAMENT]) == DeckType.TOURNAMENT
    season_id = get_season_id()
    a = archs.load_archetype(archetype_id.replace('+', ' '))
    all_archetypes = archs.load_archetypes(season_id=season_id)
    archetype_matchups = archs.load_matchups(archetype_id=a.id, season_id=season_id, tournament_only=tournament_only)
    view = Archetype(a, all_archetypes, archetype_matchups, tournament_only=tournament_only)
    return view.page()


@APP.route('/matchups/')
def matchups() -> str:
    hero: Dict[str, str] = {}
    enemy: Dict[str, str] = {}
    for k, v in request.args.items():
        if k.startswith('hero_'):
            k = k.replace('hero_', '')
            hero[k] = v
        else:
            k = k.replace('enemy_', '')
            enemy[k] = v
    season_str = request.args.get('season_id')
    season_id = int(season_str) if season_str else None
    results = mus.matchup(hero, enemy, season_id=season_id) if 'hero_person_id' in request.args else None
    matchup_archetypes = archs.load_archetypes()
    matchup_archetypes.sort(key=lambda a: a.name)
    matchup_people = list(ps.load_people(where='p.mtgo_username IS NOT NULL'))
    matchup_people.sort(key=lambda p: p.name)
    matchup_cards = cs.load_cards()
    matchup_cards.sort(key=lambda c: c.name)
    view = Matchups(hero, enemy, season_id, matchup_archetypes, matchup_people, matchup_cards, results)
    return view.page()


def validate_deck_type(s: Optional[str], allowed_values: Optional[List[DeckType]] = None) -> DeckType:
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
