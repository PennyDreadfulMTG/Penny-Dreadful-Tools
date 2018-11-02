import datetime
import logging
from typing import Dict, List, Tuple, Union

from flask import Blueprint, g, url_for
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
def add_season_id(_endpoint, values):
    values.setdefault('season_id', get_season_id())

@SEASONS.url_value_preprocessor
def pull_season_id(_endpoint, values):
    v = values.pop('season_id')
    g.season_id = rotation.season_id(v)

APP.config['SECRET_KEY'] = configuration.get('oauth2_client_secret')

try:
    oracle.init()
except DatabaseException as e:
    print("Unable to initialize oracle. I'll build it now. If this is happening on user time this is bad.", e)
    multiverse.init()
    oracle.init()

from . import api as API, admin # isort:skip # pylint: disable=wrong-import-position, unused-import
from .data import deck # isort:skip # pylint: disable=wrong-import-position

def build_menu() -> List[Dict[str, Union[str, Dict[str, str]]]]:
    archetypes_badge = None
    archetypes_badge = {'url': url_for('edit_archetypes'), 'text': '', 'badge_class': 'edit_archetypes'}
    resources_submenu: List[Dict[str, str]] = []
    if (rotation.next_rotation() - dtutil.now()) < datetime.timedelta(7) or (rotation.next_supplemental() - dtutil.now()) < datetime.timedelta(7):
        resources_submenu += [{'name': gettext('Rotation Tracking'), 'url': url_for('rotation')}]
    resources_submenu += [
        {'name': gettext('Rotation Changes'), 'url': url_for('rotation_changes')},
        {'name': gettext('Rotation Speculation'), 'url': url_for('rotation_speculation')},
        {'name': gettext('Deck Check'), 'url': url_for('deck_check')},
        {'name': gettext('Discord Chat'), 'url': 'https://discord.gg/H6EHdHu'},
        {'name': gettext('External Links'), 'url': url_for('resources')},
        {'name': gettext('Link Accounts'), 'url': url_for('link')},
        {'name': gettext('Bugs'), 'url': url_for('bugs')}
    ]
    menu = [
        {'name': gettext('Metagame'), 'url': url_for('home'), 'badge': archetypes_badge, 'submenu': [
            {'name': gettext('Latest Decks'), 'url': url_for('.decks')},
            {'name': gettext('Archetypes'), 'url': url_for('archetypes'), 'badge': archetypes_badge},
            {'name': gettext('People'), 'url': url_for('people')},
            {'name': gettext('Cards'), 'url': url_for('cards')},
            {'name': gettext('Past Seasons'), 'url': url_for('seasons')}
        ]},
        {'name': gettext('League'), 'url': url_for('league'), 'submenu': [
            {'name': gettext('League Info'), 'url': url_for('league')},
            {'name': gettext('Sign Up'), 'url': url_for('signup')},
            {'name': gettext('Report'), 'url': url_for('report')},
            {'name': gettext('Records'), 'url': url_for('current_league')},
            {'name': gettext('Retire'), 'url': url_for('retire')},
        ]},
        {'name': gettext('Competitions'), 'url': url_for('competitions'), 'submenu': [
            {'name': gettext('Competition Results'), 'url': url_for('competitions')},
            {'name': gettext('Tournament Info'), 'url': url_for('tournaments')},
            {'name': gettext('Leaderboards'), 'url': url_for('tournament_leaderboards')},
            {'name': gettext('Gatherling'), 'url': 'https://gatherling.com/'},
            {'name': gettext('Achievements'), 'url': url_for('achievements')},
            {'name': gettext('Hosting'), 'url': url_for('hosting')}
        ]},
        {'name': gettext('Resources'), 'url': url_for('resources'), 'submenu': resources_submenu},
        {'name': gettext('About'), 'url': url_for('about'), 'submenu': [
            {'name': gettext('What is Penny Dreadful?'), 'url': url_for('about')},
            {'name': gettext('About pennydreadfulmagic.com'), 'url': url_for('about_pdm')},
            {'name': gettext('FAQs'), 'url': url_for('faqs')},
            {'name': gettext('Community Guidelines'), 'url': url_for('community_guidelines')}
        ]},
        {'name': gettext('Admin'), 'admin_only': True, 'url': url_for('admin_home'), 'submenu': admin.admin_menu()}
    ]
    for item in menu:
        item['has_submenu'] = item.get('submenu') is not None
        item['is_external'] = item.get('url', '').startswith('http') and '://pennydreadfulmagic.com/' not in item['url']
        for subitem in item.get('submenu', []):
            subitem['is_external'] = subitem.get('url', '').startswith('http') and '://pennydreadfulmagic.com/' not in subitem['url']
    return menu

APP.config['menu'] = build_menu
