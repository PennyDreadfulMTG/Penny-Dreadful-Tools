import asyncio
import functools
import os
from typing import List, Optional, Tuple

from flask import Response, make_response, send_file

from decksite import APP, get_season_id
from decksite.data import playability
from decksite.views import Banners
from magic import fetcher, image_fetcher, oracle, seasons
from shared import logger
from shared.container import Container
from shared.pd_exception import DatabaseException
from shared_web.api import return_json


@APP.route('/admin/banners/')
def banner_stats() -> str:
    banners = []
    hq_crops = fetcher.hq_artcrops().keys()
    for i in range(seasons.current_season_num() + 1):
        nice_path = os.path.join(str(APP.static_folder), 'images', 'banners', f'{i}.png')
        if not os.path.exists(nice_path):
            cards, bg = banner_cards(i)
            if bg in hq_crops:
                bg += '✨'
            data = {'num': i, 'cards': cards, 'background': bg}
            banners.append(Container(data))
    view = Banners(banners)
    return view.page()

@APP.route('/banner/banner.css')
def bannercss() -> Response:
    css = 'header.season-0:before{ background-image:url("/banner/0.png");}\n'
    for i, _ in enumerate(seasons.SEASONS):
        i = i + 1
        css += f'header.season-{i}:before' + '{ background-image:' + f'url("/banner/{i}.png");' + '}\n'
    r = make_response(css)
    r.headers['Content-Type'] = 'text/css; charset=utf-8'
    return r

@APP.route('/banner/<int:seasonnum>.png')
@APP.route('/banner/<int:seasonnum>_<int:crop>.png')
def banner(seasonnum: int, crop: Optional[int] = None) -> Response:
    nice_path = os.path.join(str(APP.static_folder), 'images', 'banners', f'{seasonnum}.png')
    if os.path.exists(nice_path):
        return send_file(os.path.abspath(nice_path))
    cardnames, background = banner_cards(seasonnum)
    loop = asyncio.new_event_loop()
    path = loop.run_until_complete(image_fetcher.generate_banner(cardnames, background, crop))
    return send_file(os.path.abspath(path))

@APP.route('/banner/discord.png')
def discord_banner() -> Response:
    cardnames, background = banner_cards(get_season_id())
    loop = asyncio.new_event_loop()
    path = loop.run_until_complete(image_fetcher.generate_discord_banner(cardnames, background))
    return send_file(os.path.abspath(path))

@APP.route('/api/banner')
@APP.route('/api/banner/')
def banner_json() -> Response:
    cardnames, background = banner_cards(get_season_id())
    return return_json({
        'background': background,
        'cardnames': cardnames,
    })


def banner_cards(seasonnum: int) -> Tuple[List[str], str]:
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
    elif seasonnum == 21:
        cardnames = ["Council's Judgment", 'Ponder', 'Hymn to Tourach', 'Faithless Looting', 'Birds of Paradise', 'Dream Trawler', "Arcum's Astrolabe"]
        background = 'Drowned Catacomb'
    elif seasonnum == 22:
        cardnames = ['Daybreak Coronet', 'Brainstorm', "Bloodchief's Thirst", 'Cleansing Wildfire', 'Lovestruck Beast', 'Izzet Charm', "Smuggler's Copter"]
        background = 'Shivan Reef'
    elif seasonnum == 23:
        cardnames = ["Council's Judgment", 'Counterspell', 'Recurring Nightmare', 'Monastery Swiftspear', 'Channel', 'Meddling Mage', "Arcum's Astrolabe"]
        background = 'Adarkar Wastes'
    else:
        cardnames, background = guess_banner(seasonnum)
    return cardnames, background

@functools.lru_cache
def guess_banner(season_num: int) -> Tuple[List[str], str]:
    cardnames: List[str] = []
    picked_colors = []
    try:
        cards = playability.season_playability(season_num)
        for row in cards:
            if row['name'] in cardnames:
                continue
            c = oracle.load_card(row['name'])
            if 'Basic' in c.type_line:
                continue
            color = ''.join(c.colors)
            if color in picked_colors:
                continue
            if len(cardnames) == 7:
                return cardnames, row['name']
            cardnames.append(row['name'])
            picked_colors.append(color)
    except DatabaseException as e:
        logger.error(e)
    return ['Season of Renewal', 'Enter the Unknown', 'Unknown Shores', 'Peer through Depths'], 'New Perspectives'
