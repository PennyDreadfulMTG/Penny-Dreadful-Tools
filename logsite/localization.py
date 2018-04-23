from flask import request
from flask_babel import gettext

from . import APP, babel

LANGUAGES = [str(locale) for locale in babel.list_translations()]

@babel.localeselector
def get_locale():
    result = request.accept_languages.best_match(LANGUAGES)
    return result
