# type: ignore

import subprocess

from flask import url_for
from sqlalchemy import create_engine
from sqlalchemy_utils import create_database, database_exists

from shared import configuration
from shared_web.flask_app import PDFlask

APP = PDFlask(__name__)

APP.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
APP.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://{user}:{password}@{host}:{port}/{db}'.format(
    user=configuration.mysql_user.value,
    password=configuration.mysql_passwd.value,
    host=configuration.mysql_host.value,
    port=configuration.mysql_port.value,
    db=configuration.get('logsite_database'),
)

from . import db, stats, api, views  # isort:skip # noqa: F401

def __create_schema() -> None:
    engine = create_engine(APP.config['SQLALCHEMY_DATABASE_URI'])
    if not database_exists(engine.url):
        create_database(engine.url)
        db.DB.create_all()
    engine.dispose()


APP.config['commit-id'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'])
APP.config['branch'] = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).strip().decode()
APP.config['SECRET_KEY'] = configuration.oauth2_client_secret.value

def build_menu() -> list[dict[str, str]]:
    menu = [
        {'name': 'Home', 'url': url_for('home')},
        {'name': 'Matches', 'url': url_for('matches')},
        {'name': 'People', 'url': url_for('people')},
        {'name': 'Stats', 'url': url_for('charts')},
        {'name': 'About', 'url': url_for('about')},
    ]
    return menu


APP.config['menu'] = build_menu

with APP.app_context():
    __create_schema()
