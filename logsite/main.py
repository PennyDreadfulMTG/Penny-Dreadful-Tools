import os

from flask import redirect, send_from_directory

from . import APP


@APP.route('/favicon<rest>')
def favicon(rest):
    return send_from_directory(os.path.join(APP.root_path, 'static/images/favicon'), 'favicon{rest}'.format(rest=rest))

@APP.teardown_request
def teardown_request(response):
    return response

@APP.route('/cards/<path:name>/')
def card(name):
    return redirect('https://pennydreadfulmagic.com/cards/{name}/'.format(name=name))
