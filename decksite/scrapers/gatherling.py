import datetime
import urllib.parse
from enum import Enum
from typing import Any, Literal

import pydantic

from decksite.data import archetype, competition, deck, match, person, top
from decksite.database import db
from decksite.tournament import CompetitionFlag
from magic import decklist
from shared import dtutil, fetch_tools
from shared.database import sqlescape
from shared.pd_exception import InvalidArgumentException, InvalidDataException

Card = str
Cards = dict[Card, int]
DeckID = int
GatherlingUsername = str
FinalStandings = dict[GatherlingUsername, int]
MTGOUsername = str

class Bool(Enum):
    TRUE = 1
    FALSE = 0

class Wins(Enum):
    ZERO = 0
    ONE = 1
    TWO = 2

class Timing(Enum):
    MAIN = 1
    FINALS = 2

class Structure(Enum):
    SINGLE_ELIMINATION = 'Single Elimination'
    SWISS_BLOSSOM = 'Swiss (Blossom)'
    SWISS = 'Swiss'
    LEAGUE = 'League'
    LEAGUE_MATCH = 'League Match'

class Verification(Enum):
    VERIFIED = 'verified'
    UNVERIFIED = None  # Not actually sure what value shows when a match is not verified.

class Medal(Enum):
    WINNER = '1st'
    RUNNER_UP = '2nd'
    TOP_4 = 't4'
    TOP_8 = 't8'

class Archetype(Enum):
    AGGRO = 'Aggro'
    CONTROL = 'Control'
    COMBO = 'Combo'
    AGGRO_CONTROL = 'Aggro-Control'
    AGGRO_COMBO = 'Aggro-Combo'
    COMBO_CONTROL = 'Combo-Control'
    RAMP = 'Ramp'
    MIDRANGE = 'Midrange'
    UNCLASSIFIED = 'Unclassified'

class Format(Enum):
    PENNY_DREADFUL = 'Penny Dreadful'
    LEGACY_LEAGUE = 'Legacy League'
    STANDARD_TRIBAL_WARS = 'Standard Tribal Wars'
    CLASSIC_PAUPER = 'Classic Pauper'

@pydantic.dataclasses.dataclass
class GatherlingMatch:
    id: int
    playera: GatherlingUsername
    playera_wins: Wins
    playerb: GatherlingUsername
    playerb_wins: Wins
    timing: Timing
    round: int
    verification: Verification

@pydantic.dataclasses.dataclass
class GatherlingDeck:
    id: DeckID
    found: Bool
    playername: GatherlingUsername
    name: str
    archetype: Archetype
    notes: str
    maindeck: Cards
    sideboard: Cards

@pydantic.dataclasses.dataclass
class Finalist:
    medal: Medal
    player: GatherlingUsername
    deck: DeckID

@pydantic.dataclasses.dataclass
class Standing:
    player: GatherlingUsername
    active: Bool
    score: int
    matches_played: int
    matches_won: int
    draws: int
    games_won: int
    games_played: int
    byes: int
    OP_Match: float
    PL_Game: float
    OP_Game: float
    seed: int

@pydantic.dataclasses.dataclass
class Player:
    name: GatherlingUsername
    verified: Literal[True] | None
    discord_id: int | None
    discord_handle: str | None
    mtga_username: str | None
    mtgo_username: MTGOUsername | None

@pydantic.dataclasses.dataclass
class Event:
    name: str
    series: str
    season: int
    number: int
    format: Format
    host: str
    cohost: str | None
    active: Bool
    finalized: Bool
    current_round: int
    start: str
    mainrounds: int
    mainstruct: str
    finalrounds: int
    finalstruct: str
    mtgo_room: str
    matches: list[GatherlingMatch]
    unreported: list[str]
    decks: list[GatherlingDeck]
    finalists: list[Finalist]
    standings: list[Standing]
    players: list[Player]


APIResponse = dict[str, Event]

ALIASES: dict[str, str] = {}

def scrape(name: str | None = None) -> None:
    if name:
        data = fetch_tools.fetch_json(gatherling_url(f'/api.php?action=eventinfo&event={name}'))
        process_tournament(data['name'], Event(**data))
    else:
        data = fetch_tools.fetch_json(gatherling_url('/api.php?action=recent_events'))
        response = make_api_response(data)
        process(response)

def make_api_response(data: dict[str, dict[Any, Any]]) -> APIResponse:
    response = {}
    for k, v in data.items():
        # First check it's an event we are interested in.
        if v.get('format') == Format.PENNY_DREADFUL.value and v.get('matches') is not None and v.get('series') != 'Tribal Apocalypse':
            response[k] = Event(**v)
    return response

def process(response: APIResponse) -> None:
    for name, event in response.items():
        process_tournament(name, event)

def process_tournament(name: str, event: Event) -> None:
    name_safe = sqlescape(name)
    cs = competition.load_competitions(f'c.name = {name_safe}')
    if len(cs) > 0:
        return  # We already have this tournament, no-op out of here.
    try:
        date = vivify_date(event.start)
    except ValueError as e:
        raise InvalidDataException(f'Could not parse tournament date `{event.start}`') from e
    fs = determine_finishes(event.standings, event.finalists)
    db().begin('tournament')
    competition_id = insert_competition(name, date, event)
    decks_by_gatherling_username = insert_decks(competition_id, date, event.decks, fs, event.players)
    insert_matches(date, decks_by_gatherling_username, event.matches, event.mainrounds + event.finalrounds)
    guess_archetypes(list(decks_by_gatherling_username.values()))
    db().commit('tournament')

def determine_finishes(standings: list[Standing], finalists: list[Finalist]) -> FinalStandings:
    ps = {}
    for f in finalists:
        ps[f.player] = medal2finish(f.medal)
    r = len(ps)
    for p in standings:
        if p.player not in ps.keys():
            r += 1
            ps[p.player] = r
    return ps

def medal2finish(m: Medal) -> int:
    if m == Medal.WINNER:
        return 1
    if m == Medal.RUNNER_UP:
        return 2
    if m == Medal.TOP_4:
        return 3
    if m == Medal.TOP_8:
        return 5
    raise InvalidArgumentException(f"I don't know what the finish is for `{m}`")

def insert_competition(name: str, date: datetime.datetime, event: Event) -> int:
    if not name or not event.start or event.finalrounds is None or not event.series:
        raise InvalidDataException(f'Unable to insert Gatherling tournament `{name}` with `{event}`')
    url = gatherling_url('/eventreport.php?event=' + urllib.parse.quote(name))
    if event.finalrounds == 0:
        top_n = top.Top.NONE
    else:
        try:
            top_n = top.Top(pow(2, event.finalrounds))
        except ValueError as e:
            raise InvalidDataException(f'Unexpected number of finalrounds: `{event.finalrounds}`') from e
    competition_flag = None
    if ('Kick Off' in name or 'Kickoff' in name) and 'Season' in name:
        competition_flag = CompetitionFlag.KICK_OFF
    if 'Penny Dreadful 500' in name:
        competition_flag = CompetitionFlag.PENNY_DREADFUL_500
    if 'Super Saturday' in name:
        competition_flag = CompetitionFlag.SUPER_SATURDAY
    return competition.get_or_insert_competition(date, date, name, event.series, url, top_n, competition_flag)

def insert_decks(competition_id: int, date: datetime.datetime, ds: list[GatherlingDeck], fs: FinalStandings, players: list[Player]) -> dict[GatherlingUsername, deck.Deck]:
    return {d.playername: insert_deck(competition_id, date, d, fs, players) for d in ds}

def insert_deck(competition_id: int, date: datetime.datetime, d: GatherlingDeck, fs: FinalStandings, players: list[Player]) -> deck.Deck:
    finish = fuzzy_get(fs, d.playername)
    if not finish:
        raise InvalidDataException(f"I don't have a finish for `{d.playername}`")
    mtgo_username = find_mtgo_username(d.playername, players)
    if not mtgo_username:
        raise InvalidDataException(f"I don't have an MTGO username for `{d.playername}`")
    raw: deck.RawDeckDescription = {
        'name': d.name,
        'source': 'Gatherling',
        'competition_id': competition_id,
        'created_date': dtutil.dt2ts(date),
        'mtgo_username': mtgo_username,
        'finish': finish,
        'url': gatherling_url(f'/deck.php?mode=view&id={d.id}'),
        'archetype': d.archetype.value,
        'identifier': str(d.id),
        'cards': {'maindeck': d.maindeck, 'sideboard': d.sideboard},
    }
    if len(raw['cards']['maindeck']) + len(raw['cards']['sideboard']) == 0:
        raise InvalidDataException(f'Unable to add deck with no cards `{d.id}`')
    decklist.vivify(raw['cards'])
    if deck.get_deck_id(raw['source'], raw['identifier']):
        raise InvalidArgumentException("You asked me to insert a deck that already exists `{raw['source']}`, `{raw['identifier']}`")
    return deck.add_deck(raw)

def insert_matches(date: datetime.datetime, decks_by_gatherling_username: dict[GatherlingUsername, deck.Deck], ms: list[GatherlingMatch], total_rounds: int) -> None:
    for m in ms:
        insert_match(date, decks_by_gatherling_username, m, total_rounds)

def insert_match(date: datetime.datetime, decks_by_gatherling_username: dict[GatherlingUsername, deck.Deck], m: GatherlingMatch, total_rounds: int) -> None:
    d1 = fuzzy_get(decks_by_gatherling_username, m.playera)
    if not d1:
        raise InvalidDataException(f"I don't have a deck for `{m.playera}`")
    if is_bye(m):
        d2_id = None
        player1_wins = 2
        player2_wins = 0
    else:
        d2 = fuzzy_get(decks_by_gatherling_username, m.playerb)
        if not d2:
            raise InvalidDataException(f"I don't have a deck for `{m.playerb}`")
        d2_id = d2.id
        player1_wins = m.playera_wins.value
        player2_wins = m.playerb_wins.value
    match.insert_match(date, d1.id, player1_wins, d2_id, player2_wins, m.round, elimination(m, total_rounds))

# Account for the Gatherling API's slightly eccentric representation of byes.
def is_bye(m: GatherlingMatch) -> bool:
    return m.playera == m.playerb

# 'elimination' is an optional int with meaning: NULL = nontournament, 0 = Swiss, 8 = QF, 4 = SF, 2 = F
def elimination(m: GatherlingMatch, total_rounds: int) -> int:
    if m.timing != Timing.FINALS:
        return 0
    remaining_rounds = total_rounds - m.round + 1
    return pow(2, remaining_rounds)  # 1 => 2, 2 => 4, 3 => 8 which are the values 'elimination' expects

def find_mtgo_username(gatherling_username: GatherlingUsername, players: list[Player]) -> str:
    for p in players:
        if p.name == gatherling_username:
            if p.mtgo_username is not None:
                return aliased(p.mtgo_username)
    return aliased(gatherling_username)  # Best guess given that we don't know for certain

def gatherling_url(href: str) -> str:
    if href.startswith('http'):
        return href
    return f'https://gatherling.com{href}'

def guess_archetypes(ds: list[deck.Deck]) -> None:
    deck.calculate_similar_decks(ds)
    for d in ds:
        if d.similar_decks and d.similar_decks[0].archetype_id is not None:
            archetype.assign(d.id, d.similar_decks[0].archetype_id, None, False)

def vivify_date(s: str) -> datetime.datetime:
    return dtutil.parse(s, dtutil.GATHERLING_FORMAT, dtutil.GATHERLING_TZ)

# Work around some inconsistencies with casing in the API response.
# https://github.com/PennyDreadfulMTG/gatherling/issues/145
def fuzzy_get(d: dict[str, Any], k: str) -> Any:
    v = d.get(k)
    if v is not None:
        return v
    v = d.get(k.lower())
    if v is not None:
        return v
    d_lower = {k.lower(): v for k, v in d.items()}
    v = d_lower.get(k)
    if v is not None:
        return v
    return d_lower.get(k.lower())

# Some people have had more than one Gatherling account but want them all unified into one on pdm.
def aliased(username: str) -> str:
    if not ALIASES:
        load_aliases()
    return ALIASES.get(username, username)

def load_aliases() -> None:
    ALIASES['dummyplaceholder'] = ''  # To prevent doing the load on every lookup if there are no aliases in the db.
    for entry in person.load_aliases():
        ALIASES[entry.alias] = entry.mtgo_username
