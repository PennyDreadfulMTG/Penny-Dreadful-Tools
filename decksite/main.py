import asyncio
import logging
import os
import urllib.parse
from typing import List, Optional

from flask import (Response, abort, g, make_response, redirect, request,
                   send_file, url_for)
from werkzeug import wrappers
from werkzeug.exceptions import InternalServerError

from decksite import APP, SEASONS, auth, deck_name, get_season_id
from decksite.cache import cached
from decksite.charts import chart
from decksite.data import archetype as archs
from decksite.data import card as cs
from decksite.data import deck as ds
from decksite.data import match as ms
from decksite.data import matchup as mus
from decksite.data import news as ns
from decksite.data import person as ps
from decksite.data import season as ss
from decksite.database import db
from decksite.deck_type import DeckType
from decksite.views import (Archetype, Archetypes, Card, Cards, Deck, Decks,
                            Home, Matchups, People, Person, PersonMatches,
                            Seasons)
from magic import card as mc
from magic import image_fetcher, oracle
from shared import perf
from shared.pd_exception import (DoesNotExistException, InvalidDataException,
                                 TooFewItemsException)


@APP.route('/')
@cached()
def home() -> str:
    view = Home(ns.all_news(max_items=10), ds.latest_decks(), cs.load_cards(season_id=get_season_id()), ms.stats())
    return view.page()

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

@APP.route('/people/')
@SEASONS.route('/people/')
@cached()
def people() -> str:
    view = People(ps.load_people(season_id=get_season_id()))
    return view.page()

@APP.route('/people/<person_id>/')
@SEASONS.route('/people/<person_id>/')
@cached()
def person(person_id: str) -> str:
    p = ps.load_person_by_id_or_mtgo_username(person_id, season_id=get_season_id())
    person_cards = cs.load_cards(person_id=p.id, season_id=get_season_id())
    person_archetypes = archs.load_archetypes_deckless(person_id=p.id, season_id=get_season_id())
    all_archetypes = archs.load_archetypes_deckless(season_id=get_season_id())
    trailblazer_cards = cs.trailblazer_cards(p.id)
    unique_cards = cs.unique_cards_played(p.id)
    your_cards = {'unique': unique_cards, 'trailblazer': trailblazer_cards}
    person_matchups = archs.load_matchups(person_id=p.id, season_id=get_season_id())
    view = Person(p, person_cards, person_archetypes, all_archetypes, person_matchups, your_cards, get_season_id())
    return view.page()

@APP.route('/people/<person_id>/matches/')
@SEASONS.route('/people/<person_id>/matches/')
@cached()
def person_matches(person_id: str) -> str:
    p = ps.load_person_by_id_or_mtgo_username(person_id, season_id=get_season_id())
    matches = ms.load_matches_by_person(person_id=p.id, season_id=get_season_id())
    matches.reverse() # We want the latest at the top.
    view = PersonMatches(p, matches)
    return view.page()

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
        c = cs.load_card(oracle.valid_name(urllib.parse.unquote_plus(name)), season_id=get_season_id())
        view = Card(c, tournament_only)
        return view.page()
    except InvalidDataException as e:
        raise DoesNotExistException(e)


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

@APP.route('/export/<int:deck_id>/')
@auth.load_person
def export(deck_id: int) -> Response:
    d = ds.load_deck(deck_id)
    if d.is_in_current_run():
        if not auth.person_id() or auth.person_id() != d.person_id:
            abort(403)
    safe_name = deck_name.file_name(d)
    return make_response(mc.to_mtgo_format(str(d)), 200, {'Content-type': 'text/plain; charset=utf-8', 'Content-Disposition': 'attachment; filename={name}.txt'.format(name=safe_name)})

@APP.route('/charts/cmc/<deck_id>-cmc.png')
def cmc_chart(deck_id: int) -> Response:
    return send_file(chart.cmc(int(deck_id)))

@APP.route('/discord/')
def discord() -> wrappers.Response:
    return redirect('https://discord.gg/RxhTEEP')

@APP.route('/image/<path:c>/')
def image(c: str = '') -> wrappers.Response:
    names = c.split('|')
    try:
        requested_cards = oracle.load_cards(names)
        path = image_fetcher.download_image(requested_cards)
        if path is None:
            raise InternalServerError(f'Failed to get image for {c}')
        return send_file(os.path.abspath(path)) # Send abspath to work around monolith root versus web root.
    except TooFewItemsException as e:
        print(e)
        if len(names) == 1:
            return redirect(f'https://api.scryfall.com/cards/named?exact={c}&format=image', code=303)
        return make_response('', 400)

@APP.route('/banner/<seasonnum>.png')
def banner(seasonnum: str) -> Response:
    nice_path = os.path.join(str(APP.static_folder), 'images', 'banners', f'{seasonnum}.png')
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
    elif seasonnum == '11':
        cardnames = ['Rampaging Ferocidon', 'Frantic Search', 'Whip of Erebos', "Gaea's Revenge", 'Doomed Traveler', 'Muraganda Petroglyphs', 'Pyroclasm']
        background = 'Temple of Mystery'
    elif seasonnum == '12':
        cardnames = ['Aether Hub', 'Siege Rhino', 'Greater Good', "Mind's Desire", "God-Pharaoh's Gift", 'Kiln Fiend', 'Akroma, Angel of Wrath', 'Reanimate']
        background = 'Rofellos, Llanowar Emissary'
    elif seasonnum == '13':
        cardnames = ['Day of Judgment', 'Mana Leak', 'Duress', 'Rampaging Ferocidon', 'Evolutionary Leap', 'Gavony Township', 'Ephemerate', 'Dig Through Time', 'Lake of the Dead', 'Soulherder']
        background = 'Fact or Fiction'
    elif seasonnum == '14':
        cardnames = ['Gitaxian Probe', "Orim's Chant", 'Dark Ritual', 'Chain Lightning', 'Channel', 'Gush', 'Rofellos, Llanowar Emissary', 'Laboratory Maniac']
        background = "God-Pharaoh's Statue"
    loop = asyncio.new_event_loop()
    path = loop.run_until_complete(image_fetcher.generate_banner(cardnames, background))
    return send_file(os.path.abspath(path))

@APP.before_request
def before_request() -> None:
    g.p = perf.start()

@APP.teardown_request # type: ignore
def teardown_request(response: Response) -> Response:
    if g.get('p') is not None:
        perf.check(g.p, 'slow_page', request.path, 'decksite')
    db().close()
    return response

def validate_deck_type(s: Optional[str], allowed_values: List[DeckType] = None) -> DeckType:
    if not s:
        return DeckType.ALL
    try:
        deck_type = DeckType(s)
        if allowed_values and deck_type not in allowed_values:
            raise DoesNotExistException(f'Invalid deck_type for this endpoint: {deck_type}')
    except ValueError as e:
        raise DoesNotExistException(e)
    return deck_type

def init(debug: bool = True, port: Optional[int] = None) -> None:
    """This method is only called when initializing the dev server.  uwsgi (prod) doesn't call this method"""
    APP.logger.setLevel(logging.INFO) # pylint: disable=no-member,no-name-in-module
    APP.run(host='0.0.0.0', debug=debug, port=port)

APP.register_blueprint(SEASONS)
