import traceback
import urllib
from typing import Optional, Tuple

from flask import Flask, redirect, request, session, url_for
from github.GithubException import GithubException
from werkzeug import exceptions

from shared import repo
from shared.pd_exception import DoesNotExistException

from . import logger, oauth
from .views import InternalServerError, NotFound, Unauthorized


# pylint: disable=no-self-use, too-many-public-methods
class PDFlask(Flask):
    def __init__(self, import_name: str) -> None:
        super().__init__(import_name)
        super().register_error_handler(DoesNotExistException, self.not_found)
        super().register_error_handler(exceptions.NotFound, self.not_found)
        super().route('/unauthorized/')(self.unauthorized)
        super().route('/logout/')(self.logout)
        self.config['menu'] = []
        self.config['js_url'] = ''
        self.config['css_url'] = ''

    def not_found(self, e: Exception) -> Tuple[str, int]:
        log_exception(e)
        view = NotFound(e)
        return view.page(), 404

    def internal_server_error(self, e: Exception) -> Tuple[str, int]:
        log_exception(e)
        path = request.path
        try:
            repo.create_issue('500 error at {path}\n {e}'.format(path=path, e=e), session.get('id', 'logged_out'), 'decksite', 'PennyDreadfulMTG/perf-reports', exception=e)
        except GithubException:
            logger.error('Github error', e)
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

def log_exception(e: BaseException) -> None:
    logger.error(''.join(traceback.format_exception(type(e), e, e.__traceback__)))
