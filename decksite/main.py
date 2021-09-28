import asyncio
import functools
import logging
import os
import re
from typing import List, Optional, Set, Tuple

from flask import Response, abort, g, make_response, redirect, request, send_file, session
from werkzeug import wrappers
from werkzeug.exceptions import InternalServerError

from decksite import APP, SEASONS, auth, deck_name, get_season_id
from decksite.cache import cached
from decksite.charts import chart
from decksite.data import card as cs
from decksite.data import deck as ds
from decksite.data import match as ms
from decksite.data import news as ns
from decksite.data import playability
from decksite.database import db
from decksite.views import Home
from magic import card as mc
from magic import image_fetcher, oracle, seasons
from shared import dtutil, logger, perf
from shared.pd_exception import DatabaseException, TooFewItemsException


@APP.route('/')
@cached()
def home() -> str:
    view = Home(ns.all_news(max_items=10), ds.latest_decks(season_id=get_season_id()), cs.load_cards(season_id=get_season_id()), ms.stats())
    return view.page()

@APP.route('/export/<int:deck_id>/')
@auth.load_person
def export(deck_id: int) -> Response:
    d = ds.load_deck(deck_id)
    if d.is_in_current_run():
        if not session.get('admin') and (not auth.person_id() or auth.person_id() != d.person_id):
            abort(403)
    safe_name = deck_name.file_name(d)
    return make_response(mc.to_mtgo_format(str(d)), 200, {'Content-type': 'text/plain; charset=utf-8', 'Content-Disposition': 'attachment; filename={name}.txt'.format(name=safe_name)})

@APP.route('/charts/cmc/<deck_id>-cmc.png')
def cmc_chart(deck_id: int) -> Response:
    return send_file(chart.cmc(int(deck_id)))

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

@APP.route('/banner/banner.css')
def bannercss() -> Response:
    css = ''
    for i, _ in enumerate(seasons.SEASONS):
        i = i + 1
        css += f'header.season-{i}:before' + '{ background-image:' + f'url("/banner/{i}.png");' + '}\n'
    r = make_response(css)
    r.headers['Content-Type'] = 'text/css; charset=utf-8'
    return r

@APP.route('/banner/<int:seasonnum>.png')
def banner(seasonnum: int) -> Response:
    nice_path = os.path.join(str(APP.static_folder), 'images', 'banners', f'{seasonnum}.png')
    if os.path.exists(nice_path):
        return send_file(os.path.abspath(nice_path))
    if seasonnum == 0:
        cardnames = ['Parallax Wave', 'Treasure Cruise', 'Duress', 'Chain Lightning', 'Rofellos, Llanowar Emissary ', 'Thawing Glaciers', 'Temur Ascendancy']
        background = 'Lake of the Dead'
    elif seasonnum == 1:
        cardnames = ['Mother of Runes', 'Treasure Cruise', 'Duress', 'Lightning Strike', 'Elvish Mystic', 'Fleecemane Lion', 'Vivid Marsh']
        background = 'Dark Ritual'
    elif seasonnum == 2:
        cardnames = ['Frantic Search', 'Hymn to Tourach', "Nevinyrral's Disk", 'Winds of Rath', 'Slagstorm', 'Rise from the Tides', 'Cloudpost']
        background = 'Fact or Fiction'
    elif seasonnum == 3:
        cardnames = ['Shrine of Burning Rage', 'Terramorphic Expanse', 'Parallax Wave', 'Kambal, Consul of Allocation', 'Memory Lapse', 'Magister of Worth', 'Tendrils of Agony']
        background = 'Tidehollow Sculler'
    elif seasonnum == 4:
        cardnames = ['Hymn to Tourach', 'Emerge Unscathed', 'Ordeal of Heliod', 'Lightning Strike', 'Cruel Edict', 'Lagonna-Band Trailblazer', 'Vivid Creek']
        background = 'Vivid Creek'
    elif seasonnum == 5:
        cardnames = ['Dark Ritual', 'Cabal Ritual', 'Pyroclasm', 'Cursed Scroll', 'Necropotence', 'Harmonize', 'Precursor Golem']
        background = 'Boompile'
    elif seasonnum == 6:
        cardnames = ['Chain Lightning', 'Compulsive Research', 'Bogardan Hellkite', 'Grand Coliseum', 'Cartouche of Solidarity', 'Lagonna-Band Trailblazer', 'Felidar Guardian']
        background = 'Parallax Wave'
    elif seasonnum == 11:
        cardnames = ['Rampaging Ferocidon', 'Frantic Search', 'Whip of Erebos', "Gaea's Revenge", 'Doomed Traveler', 'Muraganda Petroglyphs', 'Pyroclasm']
        background = 'Temple of Mystery'
    elif seasonnum == 12:
        cardnames = ['Aether Hub', 'Siege Rhino', 'Greater Good', "Mind's Desire", "God-Pharaoh's Gift", 'Kiln Fiend', 'Akroma, Angel of Wrath', 'Reanimate']
        background = 'Rofellos, Llanowar Emissary'
    elif seasonnum == 13:
        cardnames = ['Day of Judgment', 'Mana Leak', 'Duress', 'Rampaging Ferocidon', 'Evolutionary Leap', 'Gavony Township', 'Ephemerate', 'Dig Through Time', 'Lake of the Dead', 'Soulherder']
        background = 'Fact or Fiction'
    elif seasonnum == 14:
        cardnames = ['Gitaxian Probe', "Orim's Chant", 'Dark Ritual', 'Chain Lightning', 'Channel', 'Gush', 'Rofellos, Llanowar Emissary', 'Laboratory Maniac']
        background = "God-Pharaoh's Statue"
    else:
        cardnames, background = guess_banner(seasonnum)
    loop = asyncio.new_event_loop()
    path = loop.run_until_complete(image_fetcher.generate_banner(cardnames, background))
    return send_file(os.path.abspath(path))

@functools.lru_cache
def guess_banner(season_num: int) -> Tuple[List[str], str]:
    cardnames: List[str] = []
    try:
        cards = playability.banner_cards(season_num)
        for row in cards:
            if row['name'] in cardnames:
                continue
            c = oracle.load_card(row['name'])
            if 'Basic' in c.type_line:
                continue
            if len(cardnames) == 7:
                return cardnames, row['name']
            cardnames.append(row['name'])
    except DatabaseException as e:
        logger.error(e)
    return ['Enter the Unknown', 'Unknown Shores', 'Peer through Depths'], 'Enter the Infinite'

@APP.before_request
def before_request() -> Optional[wrappers.Response]:
    if not request.path.endswith('/'):
        return None  # Let flask do the redirect-routes-not-ending-in-slashes thing before we interfere with routing. Avoids #8277.
    if request.path.startswith('/seasons') and len(request.path) > len('/seasons/') and get_season_id() >= seasons.current_season_num():
        return redirect(re.sub('/seasons/[^/]*', '', request.path))
    if request.path.startswith('/seasons/0'):
        return redirect(request.path.replace('/seasons/0', '/seasons/all'))
    g.p = perf.start()
    return None

@APP.after_request
def after_request(response: Response) -> Response:
    requests_until_no_intro = 20  # Typically ten page views because of async requests for the status bar.
    views = int(request.cookies.get('views', 0)) + 1
    response.set_cookie('views', str(views))
    if views >= requests_until_no_intro:
        response.set_cookie('hide_intro', value=str(True), expires=dtutil.dt2ts(dtutil.now()) + 60 * 60 * 24 * 365 * 10)
    return response

@APP.teardown_request
def teardown_request(_: Optional[BaseException]) -> None:
    if g.get('p') is not None:
        perf.check(g.p, 'slow_page', request.path, 'decksite')
    db().close()

def init(debug: bool = True, port: Optional[int] = None) -> None:
    """This method is only called when initializing the dev server.  uwsgi (prod) doesn't call this method"""
    APP.logger.setLevel(logging.INFO)  # pylint: disable=no-member,no-name-in-module
    APP.config['SESSION_COOKIE_SECURE'] = False  # Allow cookies over HTTP when running locally.
    APP.run(host='0.0.0.0', debug=debug, port=port)


APP.register_blueprint(SEASONS)
