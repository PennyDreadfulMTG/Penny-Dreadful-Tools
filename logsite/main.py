import os
import traceback

from flask import send_from_directory
from werkzeug import exceptions

from . import APP, views


@APP.route('/favicon<rest>')
def favicon(rest):
    return send_from_directory(os.path.join(APP.root_path, 'static/images/favicon'), 'favicon{rest}'.format(rest=rest))

@APP.errorhandler(exceptions.NotFound)
def not_found(e):
    traceback.print_exception(e, e, None)
    view = views.NotFound(e)
    return view.page(), 404

@APP.errorhandler(exceptions.InternalServerError)
def internal_server_error(e):
    traceback.print_exception(e, e, None)
    view = views.InternalServerError(e)
    return view.page(), 500

@APP.teardown_request
def teardown_request(response):
    return response
