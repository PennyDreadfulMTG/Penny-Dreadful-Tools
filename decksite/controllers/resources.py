from flask import Response, make_response, redirect, request, url_for
from werkzeug import wrappers

from decksite import APP, SEASONS, auth, get_season_id
from decksite import manabase as mbs
from decksite.cache import cached
from decksite.data import playability
from decksite.data import rotation as rtn
from decksite.league import DeckCheckForm
from decksite.manabase import ManabaseForm
from decksite.views import Bugs, DeckCheck, LinkAccounts, Manabase, Resources, Rotation, RotationChanges, RotationSpeculation
from magic import card, oracle
from magic import rotation as rot


@cached()
@APP.route('/rotation/')
def rotation() -> str:
    runs, num_cards = rtn.load_rotation_summary()
    view = Rotation(rot.in_rotation(), runs, num_cards)
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
def deck_check(form: DeckCheckForm | None = None) -> str:
    if form is None:
        form = DeckCheckForm(request.form, auth.person_id(), auth.mtgo_username())
    view = DeckCheck(form, auth.person_id())
    return view.page()


@APP.route('/deckcheck/', methods=['POST'])
@cached()
def do_deck_check() -> str:
    form = DeckCheckForm(request.form, auth.person_id(), auth.mtgo_username())
    form.validate()
    return deck_check(form)


@APP.route('/manabase/')
def manabase(form: ManabaseForm | None = None) -> str:
    if form is None:
        form = ManabaseForm(request.form, auth.person_id(), auth.mtgo_username())
    view = Manabase(form)
    return view.page()

@APP.route('/manabase/', methods=['POST'])
def do_manabase() -> str:
    form = ManabaseForm(request.form, auth.person_id(), auth.mtgo_username())
    if form.validate():
        form.output = mbs.find_manabase(form)
    return manabase(form)


@APP.route('/rotation/changes/')
@SEASONS.route('/rotation/changes/')
def rotation_changes() -> str | wrappers.Response:
    if get_season_id() == 0:
        return redirect(url_for('rotation_changes'))
    view = RotationChanges()
    return view.page()

@APP.route('/rotation/changes/files/<any(new,out):changes_type>/')
@SEASONS.route('/rotation/changes/files/<any(new,out):changes_type>/')
def rotation_changes_files(changes_type: str) -> Response:
    changes = oracle.pd_rotation_changes(get_season_id())[0 if changes_type == 'new' else 1]
    s = '\n'.join(f'4 {card.to_mtgo_format(c.name)}' for c in changes)
    return make_response(s, 200, {'Content-type': 'text/plain; charset=utf-8', 'Content-Disposition': f'attachment; filename={changes_type}.txt'})

@APP.route('/rotation/speculation/')
@auth.admin_required
def rotation_speculation() -> str:
    view = RotationSpeculation(oracle.if_todays_prices(out=False), oracle.if_todays_prices(out=True), playability=playability.playability())
    return view.page()

@APP.route('/rotation/speculation/files/<any(new,out):changes_type>/')
@auth.admin_required
def rotation_speculation_files(changes_type: str) -> Response:
    out = changes_type != 'new'
    changes = oracle.if_todays_prices(out=out)
    s = '\n'.join(f'4 {card.to_mtgo_format(c.name)}' for c in changes)
    return make_response(s, 200, {'Content-type': 'text/plain; charset=utf-8', 'Content-Disposition': f'attachment; filename={changes_type}.txt'})


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
