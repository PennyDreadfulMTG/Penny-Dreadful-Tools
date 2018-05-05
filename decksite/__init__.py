import logging
import subprocess

from flask import Blueprint, Flask, g
from flask_babel import Babel

from magic import multiverse, oracle, rotation
from shared import configuration
from shared.pd_exception import DatabaseException

APP = Flask(__name__)
APP.logger.setLevel(logging.WARN) # pylint: disable=no-member,no-name-in-module
BABEL = Babel(APP)
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

APP.config['commit-id'] = subprocess.check_output(['git', 'rev-parse', 'HEAD']).strip()
APP.config['branch'] = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).strip().decode()
APP.config['SECRET_KEY'] = configuration.get('oauth2_client_secret')

try:
    oracle.init()
except DatabaseException as e:
    print("Unable to initialize oracle. I'll build it now. If this is happening on user time this is bad.", e)
    multiverse.init()
    oracle.init()

from . import api as API, admin, localization # pylint: disable=wrong-import-position, unused-import
