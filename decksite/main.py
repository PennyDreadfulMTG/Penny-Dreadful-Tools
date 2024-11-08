import logging
import os
import re

import sentry_sdk
from flask import Response, abort, g, make_response, redirect, request, send_file, session
from werkzeug import wrappers
from werkzeug.exceptions import InternalServerError

from decksite import APP, SEASONS, auth, deck_name, get_season_id
from decksite.cache import cached
from decksite.data import card as cs
from decksite.data import deck as ds
from decksite.data import match as ms
from decksite.data import news as ns
from decksite.database import db
from decksite.views import Home
from magic import card as mc
from magic import image_fetcher, oracle, seasons
from shared import dtutil, logger, perf
from shared.pd_exception import TooFewItemsException


@APP.route('/')
@cached()
def home() -> str:
    decks = ds.latest_decks(season_id=get_season_id())
    top_8_plus_basics = 'LIMIT 13'
    cards, total = cs.load_cards(limit=top_8_plus_basics, season_id=get_season_id())
    view = Home(ns.all_news(decks, max_items=10), decks, cards, ms.stats())
    return view.page()

@APP.route('/export/<int:deck_id>/')
@auth.load_person
def export(deck_id: int) -> Response:
    d = ds.load_deck(deck_id)
    if d.is_in_current_run():
        if not session.get('admin') and (not auth.person_id() or auth.person_id() != d.person_id):
            abort(403)
    safe_name = deck_name.file_name(d)
    return make_response(mc.to_mtgo_format(str(d)), 200, {'Content-type': 'text/plain; charset=utf-8', 'Content-Disposition': f'attachment; filename={safe_name}.txt'})

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
        return send_file(os.path.abspath(path))  # Send abspath to work around monolith root versus web root.
    except TooFewItemsException as e:
        logger.info(f'Did not find an image for {c}: {e}')
        if len(names) == 1:
            return redirect(f'https://api.scryfall.com/cards/named?exact={c}&format=image', code=303)
        return make_response('', 400)

@APP.route('/static/dev-db.sql.gz')
def dev_db() -> wrappers.Response:
    path = os.path.join(str(APP.static_folder), 'dev-db.sql.gz')
    return send_file(os.path.abspath(path), mimetype='application/gzip', as_attachment=True)

@APP.before_request
def before_request() -> wrappers.Response | None:
    simple_paths = [APP.static_url_path, '/banner/', '/favicon.ico', '/robots.txt']
    if not any(request.path.startswith(prefix) for prefix in simple_paths):
        auth.check_perms()
    if not request.path.endswith('/'):
        return None  # Let flask do the redirect-routes-not-ending-in-slashes thing before we interfere with routing. Avoids #8277.
    if request.path.startswith('/seasons') and len(request.path) > len('/seasons/') and get_season_id() >= seasons.current_season_num():
        return redirect(re.sub('/seasons/[^/]*', '', request.path))
    if request.path.startswith('/seasons/0'):
        return redirect(request.path.replace('/seasons/0', '/seasons/all'))
    sentry_sdk.set_user({'id': auth.discord_id(), 'username': auth.mtgo_username(), 'ip_address': '{{auto}}'})
    g.p = perf.start()
    return None

@APP.after_request
def after_request(response: Response) -> Response:
    auth.migrate_session(response)
    requests_until_no_intro = 20  # Typically ten page views because of async requests for the status bar.
    views = int(request.cookies.get('views', 0)) + 1
    response.set_cookie('views', str(views))
    if views >= requests_until_no_intro:
        response.set_cookie('hide_intro', value=str(True), expires=dtutil.dt2ts(dtutil.now()) + 60 * 60 * 24 * 365 * 10)
    return response

@APP.teardown_request
def teardown_request(_: BaseException | None) -> None:
    if g.get('p') is not None:
        perf.check(g.p, 'slow_page', request.path, 'decksite')
    db().close()

def init(debug: bool = True, port: int | None = None) -> None:
    """This method is only called when initializing the dev server.  uwsgi (prod) doesn't call this method"""
    APP.logger.setLevel(logging.INFO)
    APP.config['SESSION_COOKIE_SECURE'] = False  # Allow cookies over HTTP when running locally.
    APP.run(host='0.0.0.0', debug=debug, port=port)


APP.register_blueprint(SEASONS)
