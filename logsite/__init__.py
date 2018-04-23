import subprocess
from sqlalchemy import create_engine
from sqlalchemy_utils import create_database, database_exists

from flask import Flask
from flask_babel import Babel

APP = Flask(__name__)
BABEL = Babel(APP)


from . import db, main, stats, api, localization # pylint: disable=wrong-import-position, unused-import

def __create_schema() -> None:
    engine = create_engine(APP.config['SQLALCHEMY_DATABASE_URI'])
    if not database_exists(engine.url):
        create_database(engine.url)
        db.DB.create_all()
    engine.dispose()

APP.config['commit-id'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'])

__create_schema()
