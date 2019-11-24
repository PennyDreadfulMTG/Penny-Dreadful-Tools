from typing import Optional

from flask import request

from decksite import APP, SEASONS, auth, get_season_id
from decksite.cache import cached
from decksite.data import card as cs
from decksite.league import DeckCheckForm
from decksite.views import (
    Bugs, DeckCheck, LinkAccounts, Resources, Rotation, RotationChanges)
from magic import oracle


@cached()
@APP.route('/rotation/')
@APP.route('/rotation/<interestingness>/')
def rotation(interestingness: Optional[str] = None) -> str:
    query = request.args.get('fq')
    if query is None:
        query = ''
    view = Rotation(interestingness, query)
    return view.page()


@cached()
@APP.route('/resources/')
def resources() -> str:
    view = Resources()
    return view.page()


@cached()
@APP.route('/bugs/')
def bugs() -> str:
    view = Bugs()
    return view.page()


@auth.load_person
@APP.route('/deckcheck/')
def deck_check(form: Optional[DeckCheckForm] = None) -> str:
    if form is None:
        form = DeckCheckForm(
            request.form, auth.person_id(), auth.mtgo_username())
    view = DeckCheck(form, auth.person_id())
    return view.page()


@APP.route('/deckcheck/', methods=['POST'])
@cached()
def do_deck_check() -> str:
    form = DeckCheckForm(request.form, auth.person_id(), auth.mtgo_username())
    form.validate()
    return deck_check(form)


@APP.route('/rotation/changes/')
@SEASONS.route('/rotation/changes/')
def rotation_changes() -> str:
    query = request.args.get('fq')
    if query is None:
        query = ''
    view = RotationChanges(
        *oracle.pd_rotation_changes(get_season_id()), cs.playability(), query=query)
    return view.page()


@APP.route('/rotation/speculation/')
def rotation_speculation() -> str:
    query = request.args.get('fq')
    if query is None:
        query = ''
    view = RotationChanges(oracle.if_todays_prices(out=False), oracle.if_todays_prices(
        out=True), cs.playability(), speculation=True, query=query)
    return view.page()


@APP.route('/link/')
@auth.login_required
def link() -> str:
    view = LinkAccounts()
    return view.page()


@APP.route('/link/', methods=['POST'])
@auth.login_required
def link_post() -> str:
    view = LinkAccounts()
    return view.page()
