from decksite import APP, SEASONS, auth, get_season_id
from decksite.cache import cached
from decksite.data import achievements as achs
from decksite.data import competition as comp
from decksite.data import deck as ds
from decksite.data import person as ps
from decksite.views import (PD500, Achievements, Competition, Competitions, KickOff,
                            TournamentHosting, TournamentLeaderboards, Tournaments)


@APP.route('/competitions/')
@SEASONS.route('/competitions/')
@cached()
def competitions() -> str:
    view = Competitions(comp.load_competitions(season_id=get_season_id()))
    return view.page()

@APP.route('/competitions/<competition_id>/')
@cached()
def competition(competition_id: int) -> str:
    view = Competition(comp.load_competition(competition_id))
    return view.page()

@APP.route('/tournaments/')
def tournaments() -> str:
    view = Tournaments()
    return view.page()


@APP.route('/tournaments/hosting/')
@cached()
def hosting() -> str:
    view = TournamentHosting()
    return view.page()

@APP.route('/tournaments/leaderboards/')
@SEASONS.route('/tournaments/leaderboards/')
@cached()
def tournament_leaderboards() -> str:
    leaderboards = comp.leaderboards(season_id=get_season_id())
    view = TournamentLeaderboards(leaderboards)
    return view.page()

@APP.route('/tournaments/pd500/')
@cached()
def pd500() -> str:
    tournament_winning_decks = ds.load_decks(where='d.finish = 1', season_id=get_season_id())
    view = PD500(tournament_winning_decks)
    return view.page()

@APP.route('/tournaments/kickoff/')
@cached()
def kickoff() -> str:
    view = KickOff()
    return view.page()

@APP.route('/achievements/')
@SEASONS.route('/achievements/')
def achievements() -> str:
    username = auth.mtgo_username()
    p = None
    if username is not None:
        p = ps.load_person_by_mtgo_username(username, season_id=get_season_id())
    view = Achievements(achs.load_achievements(p, season_id=get_season_id()))
    return view.page()
