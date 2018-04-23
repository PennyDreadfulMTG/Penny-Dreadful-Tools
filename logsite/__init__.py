import subprocess
from sqlalchemy import create_engine
from sqlalchemy_utils import create_database, database_exists

from flask import Flask
from flask_babel import Babel

APP = Flask(__name__)
babel = Babel(APP)


from . import db, main, stats, api, localization # pylint: disable=wrong-import-position, unused-import

APP.config['commit-id'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'])
