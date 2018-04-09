import subprocess

from flask import Blueprint, Flask, g
from flask_babel import Babel

from magic import multiverse, oracle
from shared import configuration
from shared.pd_exception import DatabaseException

APP = Flask(__name__)
BABEL = Babel(APP)
SEASON = Blueprint('season', __name__, url_prefix='/season/<season_id>')

@SEASON.url_defaults
def add_season_id(endpoint, values):
    values.setdefault('season_id', g.season_id)

@SEASON.url_value_preprocessor
def pull_season_id(endpoint, values):
    g.season_id = values.pop('season_id')

APP.config['commit-id'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'])
APP.config['SECRET_KEY'] = configuration.get('oauth2_client_secret')
try:
    oracle.init()
except DatabaseException as e:
    print("Unable to initialize oracle. I'll build it now. If this is happening on user time this is bad.", e)
    multiverse.init()
    oracle.init()

from . import api as API, localization # pylint: disable=wrong-import-position, unused-import
