from flask import (make_response, redirect, request,
                   url_for, session)

from decksite import APP, auth
from decksite.cache import cached
from decksite.data import deck as ds
from decksite.data import person as ps
from decksite import league as lg
from decksite.views import LeagueInfo, SignUp, Retire, Report
from decksite.league import ReportForm, RetireForm, SignUpForm
from shared_web.decorators import fill_cookies
from werkzeug import wrappers
from typing import Optional

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
def add_signup() -> str:
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
def add_report() -> str:
    form = ReportForm(request.form)
    if form.validate() and lg.report(form):
        response = make_response(redirect(url_for('deck', deck_id=form.entry)))
        response.set_cookie('deck_id', form.entry)
        return response
    return report(form)


@auth.login_required
@APP.route('/retire/')
@fill_cookies('deck_id')
def retire(form: Optional[RetireForm] = None, deck_id: int = None) -> str:
    if form is None:
        form = RetireForm(request.form, deck_id, session.get('id'))
    view = Retire(form)
    return view.page()


@auth.login_required
@APP.route('/retire/', methods=['POST'])
def retire_deck() -> wrappers.Response:
    form = RetireForm(request.form, discord_user=session.get('id'))
    if form.validate():
        d = ds.load_deck(form.entry)
        ps.associate(d, session['id'])
        lg.retire_deck(d)
        return redirect(url_for('signup'))
    return make_response(retire(form))
