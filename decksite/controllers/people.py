from typing import Optional

from flask import redirect, url_for
from werkzeug import wrappers

from decksite import APP, SEASONS, get_season_id
from decksite.cache import cached
from decksite.data import achievements as achs
from decksite.data import archetype as archs
from decksite.data import card as cs
from decksite.data import match as ms
from decksite.data import person as ps
from decksite.views import People, Person, PersonAchievements, PersonMatches
from shared.pd_exception import DoesNotExistException


@APP.route('/people/')
@SEASONS.route('/people/')
@cached()
def people() -> str:
    view = People(ps.load_people(season_id=get_season_id()))
    return view.page()

@APP.route('/people/<mtgo_username>/')
@APP.route('/people/id/<int:person_id>/')
@SEASONS.route('/people/<mtgo_username>/')
@SEASONS.route('/people/id/<int:person_id>/')
@cached()
def person(mtgo_username: Optional[str] = None, person_id: Optional[int] = None) -> str:
    p = load_person(mtgo_username, person_id, season_id=get_season_id())
    person_cards = cs.load_cards(person_id=p.id, season_id=get_season_id())
    person_archetypes = archs.load_archetypes_deckless(person_id=p.id, season_id=get_season_id())
    all_archetypes = archs.load_archetypes_deckless(season_id=get_season_id())
    trailblazer_cards = cs.trailblazer_cards(p.id)
    unique_cards = cs.unique_cards_played(p.id)
    your_cards = {'unique': unique_cards, 'trailblazer': trailblazer_cards}
    person_matchups = archs.load_matchups(person_id=p.id, season_id=get_season_id())
    view = Person(p, person_cards, person_archetypes, all_archetypes, person_matchups, your_cards, get_season_id())
    return view.page()

@APP.route('/people/<mtgo_username>/achievements')
@APP.route('/people/id/<int:person_id>/achievements')
@SEASONS.route('/people/<mtgo_username>/achievements')
@SEASONS.route('/people/id/<int:person_id>/achievements')
def person_achievements(mtgo_username: Optional[str] = None, person_id: Optional[int] = None) -> str:
    p = load_person(mtgo_username, person_id, season_id=get_season_id())
    view = PersonAchievements(p, achs.load_achievements(p, season_id=get_season_id(), with_detail=True))
    return view.page()

@APP.route('/person/achievements/')
def achievements_redirect() -> wrappers.Response:
    return redirect(url_for('achievements'))

@APP.route('/people/<mtgo_username>/matches/')
@APP.route('/people/id/<int:person_id>/matches/')
@SEASONS.route('/people/<mtgo_username>/matches/')
@SEASONS.route('/people/id/<int:person_id>/matches/')
@cached()
def person_matches(mtgo_username: Optional[str] = None, person_id: Optional[int] = None) -> str:
    p = load_person(mtgo_username, person_id, season_id=get_season_id())
    matches = ms.load_matches_by_person(person_id=p.id, season_id=get_season_id())
    matches.reverse() # We want the latest at the top.
    view = PersonMatches(p, matches)
    return view.page()

def load_person(mtgo_username: Optional[str] = None, person_id: Optional[int] = None, season_id: Optional[int] = None) -> ps.Person:
    if mtgo_username:
        return ps.load_person_by_mtgo_username(mtgo_username, season_id=season_id)
    if person_id:
        return ps.load_person_by_id(person_id, season_id=season_id)
    raise DoesNotExistException(f"Can't load a person with `{mtgo_username}` and `{person_id}`.")
