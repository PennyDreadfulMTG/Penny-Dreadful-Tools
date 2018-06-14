from flask import redirect

from . import APP

@APP.route('/cards/<path:name>/')
def card(name):
    return redirect('https://pennydreadfulmagic.com/cards/{name}/'.format(name=name))
