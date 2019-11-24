from flask import redirect, url_for
from werkzeug import wrappers

from decksite import APP, SEASONS, auth, get_season_id
from decksite.cache import cached
from decksite.data import achievements as achs
from decksite.data import competition as comp

from decksite.data import person as ps
from decksite.views import (Achievements,
                            Competition, Competitions, PersonAchievements,
                            TournamentHosting, TournamentLeaderboards,
                            Tournaments)

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

@APP.route('/achievements/')
@SEASONS.route('/achievements/')
def achievements() -> str:
    username = auth.mtgo_username()
    p = None
    if username is not None:
        p = ps.load_person_by_mtgo_username(username, season_id=get_season_id())
    view = Achievements(achs.load_achievements(p, season_id=get_season_id()))
    return view.page()

@APP.route('/people/<person_id>/achievements')
@SEASONS.route('/people/<person_id>/achievements')
def person_achievements(person_id: str) -> str:
    p = ps.load_person_by_id_or_mtgo_username(person_id, season_id=get_season_id())
    view = PersonAchievements(p, achs.load_achievements(p, season_id=get_season_id(), with_detail=True))
    return view.page()

@APP.route('/person/achievements/')
def achievements_redirect() -> wrappers.Response:
    return redirect(url_for('achievements'))
