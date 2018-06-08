from flask import redirect

from . import APP


@APP.teardown_request
def teardown_request(response):
    return response

@APP.route('/cards/<path:name>/')
def card(name):
    return redirect('https://pennydreadfulmagic.com/cards/{name}/'.format(name=name))
