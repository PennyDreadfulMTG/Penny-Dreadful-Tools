from typing import Optional

from flask import make_response, redirect, request, session, url_for, Response
from werkzeug import wrappers

from decksite import APP, auth
from decksite import league as lg
from decksite.cache import cached
from decksite.data import deck as ds
from decksite.data import person as ps
from decksite.league import ReportForm, RetireForm, SignUpForm
from decksite.views import LeagueInfo, Report, Retire, SignUp
from shared_web.decorators import fill_cookies


@APP.route('/league/')
def league() -> str:
    view = LeagueInfo()
    return view.page()


@APP.route('/league/current/')
@cached()
def current_league() -> wrappers.Response:
    url = url_for('competition', competition_id=lg.active_league().id)
    return redirect(url)

@APP.route('/signup/')
@auth.load_person
def signup(form: Optional[SignUpForm] = None) -> str:
    if form is None:
        form = SignUpForm(request.form, auth.person_id(), auth.mtgo_username())
    view = SignUp(form, lg.get_status() == lg.Status.CLOSED, auth.person_id())
    return view.page()


@APP.route('/signup/', methods=['POST'])
@cached()
def add_signup() -> Response:
    if lg.get_status() == lg.Status.CLOSED:
        return signup()
    form = SignUpForm(request.form, auth.person_id(), auth.mtgo_username())
    if form.validate():
        d = lg.signup(form)
        response = make_response(redirect(url_for('deck', deck_id=d.id)))
        response.set_cookie('deck_id', str(d.id))
        return response
    return signup(form)


@APP.route('/report/')
@auth.load_person
@fill_cookies('deck_id')
def report(form: Optional[ReportForm] = None, deck_id: int = None) -> str:
    if form is None:
        form = ReportForm(request.form, deck_id, auth.person_id())
    view = Report(form, auth.person_id())
    return view.page()


@APP.route('/report/', methods=['POST'])
def add_report() -> Response:
    form = ReportForm(request.form)
    if form.validate() and lg.report(form):
        response = make_response(redirect(url_for('deck', deck_id=form.entry)))
        response.set_cookie('deck_id', form.entry)
        return response
    return report(form)


@APP.route('/retire/')
@fill_cookies('deck_id')
@auth.login_required
def retire(form: Optional[RetireForm] = None, deck_id: int = None) -> str:
    if form is None:
        form = RetireForm(request.form, deck_id, session.get('id'))
    view = Retire(form)
    return view.page()


@APP.route('/retire/', methods=['POST'])
@auth.login_required
def retire_deck() -> wrappers.Response:
    form = RetireForm(request.form, discord_user=session.get('id'))
    if form.validate():
        d = ds.load_deck(form.entry)
        ps.associate(d, session['id'])
        lg.retire_deck(d)
        return redirect(url_for('signup'))
    return make_response(retire(form))
