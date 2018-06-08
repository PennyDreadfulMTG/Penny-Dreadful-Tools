import os
import subprocess
import traceback
import urllib
from typing import Optional, Tuple

from flask import Flask, redirect, request, session, url_for
from flask_babel import Babel
from github.GithubException import GithubException
from werkzeug import exceptions

from shared import configuration, repo
from shared.pd_exception import DoesNotExistException

from . import api, localization, logger, oauth
from .api import generate_error, return_json
from .views import InternalServerError, NotFound, Unauthorized


# pylint: disable=no-self-use, too-many-public-methods
class PDFlask(Flask):
    def __init__(self, import_name: str) -> None:
        super().__init__(import_name)
        super().register_error_handler(DoesNotExistException, self.not_found)
        super().register_error_handler(exceptions.NotFound, self.not_found)
        super().register_error_handler(exceptions.InternalServerError, self.internal_server_error)
        super().route('/unauthorized/')(self.unauthorized)
        super().route('/logout/')(self.logout)
        super().route('/authenticate/')(self.authenticate)
        super().route('/authenticate/callback/')(self.authenticate_callback)
        super().route('/api/gitpull', methods=['POST'])(api.process_github_webhook)
        super().route('/api/commit')(api.commit_id)
        self.config['menu'] = []
        self.config['js_url'] = ''
        self.config['css_url'] = ''
        self.config['commit-id'] = subprocess.check_output(['git', 'rev-parse', 'HEAD']).strip().decode()
        self.config['branch'] = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).strip().decode()
        self.config['SESSION_COOKIE_DOMAIN'] = configuration.get_optional_str('flask_cookie_domain')

        translations = os.path.abspath(os.path.join(os.path.dirname(__file__), 'translations'))
        self.config['BABEL_TRANSLATION_DIRECTORIES'] = translations
        self.babel = Babel(self)
        localization.init(self.babel)

    def not_found(self, e: Exception) -> Tuple[str, int]:
        if request.path.startswith('/error/HTTP'):
            return return_json(generate_error('NOTSUPPORTED', 'Not supported'), status=404)
        log_exception(e)
        if request.path.startswith('/api/'):
            return return_json(generate_error('NOTFOUND', 'Endpoint not found'), status=404)
        view = NotFound(e)
        return view.page(), 404

    def internal_server_error(self, e: Exception) -> Tuple[str, int]:
        log_exception(e)
        path = request.path
        try:
            repo.create_issue('500 error at {path}\n {e}'.format(path=path, e=e), session.get('mtgo_username', session.get('id', 'logged_out')), self.name, 'PennyDreadfulMTG/perf-reports', exception=e)
        except GithubException:
            logger.error('Github error', e)
        if request.path.startswith('/api/'):
            return return_json(generate_error('INTERNALERROR', 'Internal Error.', exception=e), status=404)
        view = InternalServerError(e)
        return view.page(), 500

    def unauthorized(self, error: Optional[str] = None) -> str:
        view = Unauthorized(error)
        return view.page()

    def logout(self):
        oauth.logout()
        target = request.args.get('target', 'home')
        if bool(urllib.parse.urlparse(target).netloc):
            return redirect(target)
        return redirect(url_for(target))

    def authenticate(self):
        target = request.args.get('target')
        authorization_url, state = oauth.setup_authentication()
        session['oauth2_state'] = state
        if target is not None:
            session['target'] = target
        response = redirect(authorization_url)
        # Google doesn't like the discordapp.com page we redirect to being disallowed in discordapp.com's robots.txt without `X-Robots-Tag: noindex` in our response.
        # See https://support.google.com/webmasters/answer/93710
        response.headers['X-Robots-Tag'] = 'noindex'
        return response

    def authenticate_callback(self):
        if request.values.get('error'):
            return redirect(url_for('unauthorized', error=request.values['error']))
        oauth.setup_session(request.url)
        url = session.get('target')
        if url is None:
            url = url_for('home')
        session['target'] = None
        return redirect(url)


def log_exception(e: BaseException) -> None:
    logger.error(''.join(traceback.format_exception(type(e), e, e.__traceback__)))
