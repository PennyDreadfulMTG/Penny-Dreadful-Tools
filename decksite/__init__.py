import datetime
import logging
from typing import Any, Dict, List, Tuple, Union, cast

from flask import Blueprint, g, request, url_for
from flask_babel import gettext, ngettext

from magic import multiverse, oracle, rotation
from shared import configuration, dtutil
from shared.pd_exception import DatabaseException
from shared_web.flask_app import PDFlask

APP = PDFlask(__name__)
APP.logger.setLevel(logging.WARN) # pylint: disable=no-member,no-name-in-module
SEASONS = Blueprint('seasons', __name__, url_prefix='/seasons/<season_id>')

def get_season_id() -> int:
    return g.get('season_id', rotation.current_season_num())

@SEASONS.url_defaults
def add_season_id(_endpoint: str, values: Dict[str, Any]) -> None:
    values.setdefault('season_id', get_season_id())

@SEASONS.url_value_preprocessor
def pull_season_id(_endpoint: str, values: Dict[str, Any]) -> None:
    v = values.pop('season_id')
    g.season_id = rotation.season_id(v)

APP.config['SECRET_KEY'] = configuration.get('oauth2_client_secret')

def build_menu() -> List[Dict[str, Union[str, Dict[str, str]]]]:
    current_template = (request.endpoint or '').replace('seasons.', '')
    archetypes_badge = {'endpoint': 'edit_archetypes', 'text': '', 'badge_class': 'edit_archetypes'}
    resources_submenu: List[Dict[str, str]] = []
    if (rotation.next_rotation() - dtutil.now()) < datetime.timedelta(7) or (rotation.next_supplemental() - dtutil.now()) < datetime.timedelta(7):
        resources_submenu += [{'name': gettext('Rotation Tracking'), 'endpoint': 'rotation'}]
    resources_submenu += [
        {'name': gettext('Rotation Changes'), 'endpoint': 'rotation_changes'},
        {'name': gettext('Rotation Speculation'), 'endpoint': 'rotation_speculation'},
        {'name': gettext('Deck Check'), 'endpoint': 'deck_check'},
        {'name': gettext('Discord Chat'), 'url': 'https://discord.gg/H6EHdHu'},
        {'name': gettext('External Links'), 'endpoint': 'resources'},
        {'name': gettext('Link Accounts'), 'endpoint': 'link'},
        {'name': gettext('Bugs'), 'endpoint': 'bugs'}
    ]
    menu = [
        {'name': gettext('Metagame'), 'endpoint': 'home', 'badge': archetypes_badge, 'submenu': [
            {'name': gettext('Decks'), 'endpoint': '.decks'},
            {'name': gettext('Archetypes'), 'endpoint': 'archetypes', 'badge': archetypes_badge},
            {'name': gettext('People'), 'endpoint': 'people'},
            {'name': gettext('Cards'), 'endpoint': 'cards'},
            {'name': gettext('Past Seasons'), 'endpoint': 'seasons'},
            {'name': gettext('Matchups'), 'endpoint': 'matchups'},
        ]},
        {'name': gettext('League'), 'endpoint': 'league', 'submenu': [
            {'name': gettext('League Info'), 'endpoint': 'league'},
            {'name': gettext('Sign Up'), 'endpoint': 'signup'},
            {'name': gettext('Report'), 'endpoint': 'report'},
            {'name': gettext('Records'), 'endpoint': 'current_league'},
            {'name': gettext('Retire'), 'endpoint': 'retire'},
        ]},
        {'name': gettext('Competitions'), 'endpoint': 'competitions', 'submenu': [
            {'name': gettext('Competition Results'), 'endpoint': 'competitions'},
            {'name': gettext('Tournament Info'), 'endpoint': 'tournaments'},
            {'name': gettext('Leaderboards'), 'endpoint': 'tournament_leaderboards'},
            {'name': gettext('Gatherling'), 'url': 'https://gatherling.com/'},
            {'name': gettext('Achievements'), 'endpoint': 'achievements'},
            {'name': gettext('Hosting'), 'endpoint': 'hosting'}
        ]},
        {'name': gettext('Resources'), 'endpoint': 'resources', 'submenu': resources_submenu},
        {'name': gettext('About'), 'endpoint': 'about', 'submenu': [
            {'name': gettext('What is Penny Dreadful?'), 'endpoint': 'about'},
            {'name': gettext('About pennydreadfulmagic.com'), 'endpoint': 'about_pdm'},
            {'name': gettext('FAQs'), 'endpoint': 'faqs'},
            {'name': gettext('Community Guidelines'), 'endpoint': 'community_guidelines'}
        ]},
        {'name': gettext('Admin'), 'admin_only': True, 'endpoint': 'admin_home', 'submenu': admin.admin_menu()}
    ]
    setup_links(menu)
    for item in menu:
        item['current'] = item.get('endpoint', '').replace('seasons', '').replace('.', '') == current_template or current_template in [entry.get('endpoint', '') for entry in item.get('submenu', [])]
        item['has_submenu'] = item.get('submenu') is not None
    return menu

def setup_links(menu: List[Dict[str, Any]]) -> None:
    for item in menu:
        if item.get('endpoint'):
            item['url'] = url_for(item.get('endpoint', ''))
        item['is_external'] = cast(str, item.get('url', '')).startswith('http') and '://pennydreadfulmagic.com/' not in item['url']
        setup_links(item.get('submenu', []))

try:
    oracle.init()
except DatabaseException as e:
    print("Unable to initialize oracle. I'll build it now. If this is happening on user time this is bad.", e)
    multiverse.init()
    oracle.init()

from decksite.controllers import admin  # isort:skip # pylint: disable=wrong-import-position
from . import api as API # isort:skip # pylint: disable=wrong-import-position, unused-import
from .data import deck # isort:skip # pylint: disable=wrong-import-position
APP.config['menu'] = build_menu
