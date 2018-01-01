import subprocess

from flask import Flask

from magic import oracle
from shared import configuration

APP = Flask(__name__)
APP.config['commit-id'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'])
APP.config['SECRET_KEY'] = configuration.get('oauth2_client_secret')
oracle.init()

from . import api as API # pylint: disable=wrong-import-position, unused-import
