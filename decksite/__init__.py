import subprocess

from flask import Flask

from magic import multiverse, oracle
from shared import configuration
from shared.pd_exception import DatabaseException

APP = Flask(__name__)
APP.config['commit-id'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'])
APP.config['SECRET_KEY'] = configuration.get('oauth2_client_secret')
try:
    oracle.init()
except DatabaseException as e:
    print("Unable to initialize oracle. I'll build it now. If this is happening on user time this is bad.", e)
    multiverse.init()
    oracle.init()

from . import api as API # pylint: disable=wrong-import-position, unused-import
