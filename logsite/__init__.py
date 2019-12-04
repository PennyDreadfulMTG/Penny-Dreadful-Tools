import subprocess
from typing import Dict, List, Union

from flask import url_for
from sqlalchemy import create_engine
from sqlalchemy_utils import create_database, database_exists

from shared import configuration
from shared_web.flask_app import PDFlask

APP = PDFlask(__name__)

APP.config['DATABASE_URI'] = 'mysql://{user}:{password}@{host}:{port}/{db}'.format(
    user=configuration.get('mysql_user'),
    password=configuration.get('mysql_passwd'),
    host=configuration.get('mysql_host'),
    port=configuration.get('mysql_port'),
    db=configuration.get('logsite_database'))

from . import db, stats, api, views # isort:skip # pylint: disable=wrong-import-position, unused-import

def __create_schema() -> None:
    pass

APP.config['commit-id'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'])
APP.config['branch'] = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).strip().decode()
APP.config['SECRET_KEY'] = configuration.get('oauth2_client_secret')

def build_menu() -> List[Dict[str, Union[str, Dict[str, str]]]]:
    menu = [
        {'name': 'Home', 'url': url_for('home')},
        {'name': 'Matches', 'url': url_for('matches')},
        {'name': 'People', 'url': url_for('people')},
        {'name': 'Stats', 'url': url_for('charts')},
        {'name': 'About', 'url': url_for('about')},
    ]
    return menu

APP.config['menu'] = build_menu

__create_schema()
