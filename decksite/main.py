import logging
import os
import re
from copy import copy

import sentry_sdk
from flask import Response, abort, g, make_response, redirect, request, send_file, session
from werkzeug import wrappers
from werkzeug.exceptions import InternalServerError

from decksite import APP, SEASONS, auth, deck_name, get_season_id
from decksite.cache import cached
from decksite.data import archetype as archs
from decksite.data import card as cs
from decksite.data import deck as ds
from decksite.data import match as ms
from decksite.data import news as ns
from decksite.database import db
from decksite.views import Home
from magic import card as mc
from magic import image_fetcher, oracle, seasons
from shared import logger, perf
from shared.pd_exception import TooFewItemsException

SUPPORTED_IMAGE_VERSIONS = ['', 'art_crop']
# Card images never change once we've picked a printing, so let browsers and Cloudflare hang on to them.
# Without this every card on every page is revalidated against us on every pageview.
IMAGE_MAX_AGE = 60 * 60 * 24 * 7


@APP.route('/')
@cached()
def home() -> str:
    season_id = get_season_id()
    decks = ds.latest_decks(season_id=season_id)
    top_8_plus_basics = 'LIMIT 13'
    cards, total = cs.load_cards_with_total(limit=top_8_plus_basics, season_id=season_id)
    movers_and_shakers = archs.load_movers_and_shakers(season_id)
    view = Home(ns.all_news(decks, max_items=10), decks, cards, ms.stats(), movers_and_shakers)
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
    version = request.args.get('version', '')
    if version not in SUPPORTED_IMAGE_VERSIONS:
        return make_response('', 400)
    if version == 'art_crop' and len(names) > 1:
        return make_response('', 400)  # There's no such thing as a composite art crop.
    try:
        requested_cards = oracle.load_cards(names)
        preferred_printing = request.args.get('printing')
        preferred_printing_system_id = request.args.get('printing_id')
        if preferred_printing or preferred_printing_system_id:
            requested_cards = [copy(card) for card in requested_cards]
            for card in requested_cards:
                if preferred_printing:
                    card['preferred_printing'] = preferred_printing
                if preferred_printing_system_id:
                    card['preferred_printing_system_id'] = preferred_printing_system_id
        path = image_fetcher.download_image(requested_cards, version=version)
        if path is None:
            if len(names) == 1:
                # Almost always a Scryfall 429 on a cold cache. Let the visitor's browser fetch this one
                # itself, from its own IP, rather than showing a broken image and paging someone.
                logger.warning(f'Could not fetch image for {c}, redirecting to Scryfall')
                return scryfall_fallback(c, version)
            raise InternalServerError(f'Failed to get image for {c}')
        response = send_file(os.path.abspath(path))  # Send abspath to work around monolith root versus web root.
        # send_file defaults to no-cache, which wins over any max-age we add and makes browsers revalidate
        # every image on every pageview. Clear it. (send_file has a max_age argument but types-flask predates it.)
        response.cache_control.no_cache = None
        response.cache_control.public = True
        response.cache_control.max_age = IMAGE_MAX_AGE
        return response
    except TooFewItemsException as e:
        logger.info(f'Did not find an image for {c}: {e}')
        if len(names) == 1:
            return scryfall_fallback(c, version)
        return make_response('', 400)

def scryfall_fallback(name: str, version: str) -> wrappers.Response:
    """Redirect the browser to Scryfall for a single card image we can't serve ourselves.

    This is the old behaviour for every image, kept as the fallback. It's uncached, so the next
    request comes back to us and gets served locally once the fetch succeeds."""
    url = f'https://api.scryfall.com/cards/named?exact={name}&format=image'
    if version:
        url += f'&version={version}'
    return redirect(url, code=303)

@APP.route('/static/dev-db.sql.gz')
def dev_db() -> wrappers.Response:
    path = os.path.join(str(APP.static_folder), 'dev-db.sql.gz')
    return send_file(os.path.abspath(path), mimetype='application/gzip', as_attachment=True)

@APP.before_request
def before_request() -> wrappers.Response | None:
    # These serve identical bytes to everyone. Touching the session would add a Vary: Cookie that stops
    # them being cached by Cloudflare, so return before anything looks at it.
    simple_paths = [APP.static_url_path, '/banner/', '/favicon.ico', '/robots.txt', '/image/']
    if any(request.path.startswith(prefix) for prefix in simple_paths):
        return None
    auth.check_perms()
    if not request.path.endswith('/'):
        return None  # Let flask do the redirect-routes-not-ending-in-slashes thing before we interfere with routing. Avoids #8277.
    if request.path.startswith('/seasons') and len(request.path) > len('/seasons/') and get_season_id() >= seasons.current_season_num():
        return redirect(re.sub('/seasons/[^/]*', '', request.path))
    if re.match(r'^/seasons/all/decks(/.*)?$', request.path):
        return redirect(re.sub(r'^/seasons/all', '', request.path))
    if request.path.startswith('/seasons/0'):
        return redirect(request.path.replace('/seasons/0', '/seasons/all'))
    sentry_sdk.set_user({'id': auth.discord_id(), 'username': auth.mtgo_username(), 'ip_address': '{{auto}}'})
    g.p = perf.start()
    return None

# @APP.after_request
# def after_request(response: Response) -> Response:
#     return response

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
