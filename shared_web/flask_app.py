import os
import subprocess
import urllib
from typing import Any, Dict, Optional, Tuple, Union

import sentry_sdk
from flask import (Blueprint, Flask, Request, Response, redirect, request, send_from_directory,
                   session, url_for)
from flask_babel import Babel
from flask_restx import Api
from github.GithubException import GithubException
from werkzeug import exceptions, wrappers

from shared import configuration, logger, repo
from shared.pd_exception import DoesNotExistException

from . import api, localization, oauth
from .api import generate_error, return_json
from .views import InternalServerError, NotFound, Unauthorized


# pylint: disable=no-self-use, too-many-public-methods
class PDFlask(Flask):
    def __init__(self, import_name: str) -> None:
        shared_web_path = os.path.abspath(os.path.dirname(__file__))
        static_folder = os.path.join(shared_web_path, 'static')
        super().__init__(import_name, static_folder=static_folder)
        super().register_error_handler(DoesNotExistException, self.not_found)
        super().register_error_handler(exceptions.NotFound, self.not_found)
        super().register_error_handler(exceptions.InternalServerError, self.internal_server_error)
        super().route('/unauthorized/')(self.unauthorized)
        super().route('/logout/')(self.logout)
        super().route('/authenticate/')(self.authenticate)
        super().route('/authenticate/callback/')(self.authenticate_callback)
        super().route('/api/gitpull', methods=['POST'])(api.process_github_webhook)
        super().route('/api/commit')(api.commit_id)
        super().route('/robots.txt')(self.robots_txt)
        super().route('/favicon<rest>')(self.favicon)
        self.url_build_error_handlers.append(self.external_url_handler)
        if self.config.get('SERVER_NAME') is None:
            self.config['SERVER_NAME'] = configuration.get_optional_str('flask_server_name')
        self.config['menu'] = []
        self.config['js_url'] = ''
        self.config['css_url'] = ''
        self.config['commit-id'] = subprocess.check_output(['git', 'rev-parse', 'HEAD']).strip().decode()
        self.config['branch'] = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).strip().decode()
        self.config['SESSION_COOKIE_DOMAIN'] = configuration.get_optional_str('flask_cookie_domain')
        # Set some sensible cookie options. See https://flask.palletsprojects.com/en/master/security/
        self.config['SESSION_COOKIE_SECURE'] = True
        self.config['SESSION_COOKIE_HTTPONLY'] = False # We want to be able to set the page_size cookie in an API response.
        self.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

        translations = os.path.abspath(os.path.join(shared_web_path, 'translations'))
        self.config['BABEL_TRANSLATION_DIRECTORIES'] = translations
        self.babel = Babel(self)
        localization.init(self.babel)
        self.api_root = Blueprint('api', import_name, url_prefix='/api/')
        self.api = Api(self.api_root, title=f'{import_name} API', default=import_name)
        self.register_blueprint(self.api_root)

    def not_found(self, e: Exception) -> Union[Response, Tuple[str, int]]:
        if request.path.startswith('/error/HTTP_BAD_GATEWAY'):
            return return_json(generate_error('BADGATEWAY', 'Bad Gateway'), status=502)
        logger.warning('404 Not Found ' + request.path)
        if request.path.startswith('/api/'):
            return return_json(generate_error('NOTFOUND', 'Endpoint not found'), status=404)
        view = NotFound(e)
        return view.page(), 404

    def internal_server_error(self, e: Exception) -> Union[Tuple[str, int], Response]:
        log_exception(request, e)
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

    def logout(self) -> wrappers.Response:
        oauth.logout()
        target = request.args.get('target', 'home')
        if bool(urllib.parse.urlparse(target).netloc):
            return redirect(target)
        return redirect(url_for(target))

    def authenticate(self) -> wrappers.Response:
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

    def authenticate_callback(self) -> wrappers.Response:
        if request.values.get('error'):
            return redirect(url_for('unauthorized', error=request.values['error']))
        oauth.setup_session(request.url)
        url = session.get('target')
        if url is None:
            url = url_for('home')
        session['target'] = None
        return redirect(url)

    def robots_txt(self) -> Response:
        """
        Serves the robots.txt
        """
        if configuration.get_bool('is_test_site'):
            return send_from_directory(self.static_folder, 'deny-all-robots.txt')
        return send_from_directory(self.static_folder, 'robots.txt')

    def favicon(self, rest: str) -> Response:
        if not self.static_folder:
            raise DoesNotExistException()
        return send_from_directory(os.path.join(self.static_folder, 'images', 'favicon'), 'favicon{rest}'.format(rest=rest))

    def external_url_handler(self, error: Exception, endpoint: str, values: Dict[str, Any]) -> str:
        """Looks up an external URL when `url_for` cannot build a URL."""
        url = self.lookup_external_url(endpoint, **values)
        if url is None:
            # External lookup did not have a URL.
            # Re-raise the BuildError, in context of original traceback.
            raise error
        # url_for will use this result, instead of raising BuildError.
        return url

    def lookup_external_url(self, endpoint: str, **values: Dict[str, Any]) -> Optional[str]:
        if endpoint == 'card': # The error pages make a /cards/<name> reference, but only decksite implements it.
            return 'https://pennydreadfulmagic.com/cards/{name}/'.format(name=values['name'])
        return None

def log_exception(r: Request, e: Exception) -> None:
    logger.error(f'At request path: {r.path}', repo.format_exception(e))
