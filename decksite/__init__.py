import datetime
import logging
from typing import Any

from flask import Blueprint, g, request, url_for
from flask_babel import gettext

from magic import multiverse, oracle, seasons
from shared import configuration, dtutil
from shared.pd_exception import DatabaseException
from shared_web.flask_app import PDFlask
from shared_web.menu import Menu, Badge, MenuItem

APP = PDFlask(__name__)
APP.logger.setLevel(logging.WARN)
SEASONS = Blueprint('seasons', __name__, url_prefix='/seasons/<season_id>')

def get_season_id() -> int:
    season_id = g.get('season_id', seasons.current_season_num())
    if season_id == 'all':
        return 0
    return season_id

@SEASONS.url_defaults
def add_season_id(_endpoint: str, values: dict[str, Any]) -> None:
    values.setdefault('season_id', get_season_id())

@SEASONS.url_value_preprocessor
def pull_season_id(_endpoint: str | None, values: dict[Any, Any] | None) -> None:
    if values is None:
        return
    v = values.pop('season_id')
    g.season_id = seasons.season_id(v)


APP.config['SECRET_KEY'] = configuration.oauth2_client_secret.value

def build_menu() -> Menu:
    archetypes_badge = Badge(url_for('edit_archetypes'), '', 'edit_archetypes')
    resources_submenu_items = []
    if (seasons.next_rotation() - dtutil.now()) < datetime.timedelta(7):
        resources_submenu_items.append(MenuItem(gettext('Rotation Tracking'), endpoint='rotation'))
    resources_submenu_items += [
        MenuItem(gettext('Rotation Changes'), endpoint='rotation_changes'),
        MenuItem(gettext('Deck Check'), endpoint='deck_check'),
        MenuItem(gettext('Discord Chat'), url='https://discord.gg/H6EHdHu'),
        MenuItem(gettext('External Links'), endpoint='resources'),
        MenuItem(gettext('Link Accounts'), endpoint='link'),
        MenuItem(gettext('Bugs'), endpoint='bugs'),
    ]
    menu = Menu(menu=[
        MenuItem(gettext('Home'), endpoint='home'),
        MenuItem(gettext('Metagame'), endpoint='metagame', badge=archetypes_badge, submenu=Menu([
            MenuItem(gettext('Meta'), endpoint='.metagame'),
            MenuItem(gettext('Decks'), endpoint='.decks'),
            MenuItem(gettext('Archetypes'), endpoint='.archetypes', badge=archetypes_badge),
            MenuItem(gettext('People'), endpoint='.people'),
            MenuItem(gettext('Cards'), endpoint='.cards'),
            MenuItem(gettext('Past Seasons'), endpoint='seasons'),
            MenuItem(gettext('Matchups'), endpoint='matchups'),
        ])),
        MenuItem(gettext('League'), endpoint='league', submenu=Menu([
            MenuItem(gettext('League Info'), endpoint='league'),
            MenuItem(gettext('Sign Up'), endpoint='signup'),
            MenuItem(gettext('Report'), endpoint='report'),
            MenuItem(gettext('Records'), endpoint='current_league'),
            MenuItem(gettext('Retire'), endpoint='retire'),
        ])),
        MenuItem(gettext('Competitions'), endpoint='competitions', submenu=Menu([
            MenuItem(gettext('Competition Results'), endpoint='competitions'),
            MenuItem(gettext('Tournament Info'), endpoint='tournaments'),
            MenuItem(gettext('Leaderboards'), endpoint='tournament_leaderboards'),
            MenuItem(gettext('Gatherling'), url='https://gatherling.com/'),
            MenuItem(gettext('Achievements'), endpoint='achievements'),
            MenuItem(gettext('Hosting'), endpoint='hosting'),
        ])),
        MenuItem(gettext('Resources'), endpoint='resources', submenu=Menu(resources_submenu_items)),
        MenuItem(gettext('About'), endpoint='about', submenu=Menu([
            MenuItem(gettext('What is Penny Dreadful?'), endpoint='about'),
            MenuItem(gettext('About pennydreadfulmagic.com'), endpoint='about_pdm'),
            MenuItem(gettext('FAQs'), endpoint='faqs'),
            MenuItem(gettext('Community Guidelines'), endpoint='community_guidelines'),
            MenuItem(gettext('Contact Us'), endpoint='contact_us'),
        ])),
        MenuItem(gettext('Admin'), endpoint='admin_home', submenu=admin.admin_menu(), permission_required='demimod'),
    ], current_endpoint=request.endpoint)
    return menu


try:
    oracle.init()
except DatabaseException as e:
    APP.logger.warning("Unable to initialize oracle. I'll build it now. If this is happening on user time this is bad.", e)
    multiverse.init()
    oracle.init()

from decksite.controllers import admin  # isort:skip
from .data import deck  # isort:skip # noqa: F401
APP.config['menu'] = build_menu
