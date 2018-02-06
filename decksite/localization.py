from . import APP, babel
from flask_babel import gettext
from flask import request

LANGUAGES = [str(locale) for locale in babel.list_translations()]

@babel.localeselector
def get_locale():
    result = request.accept_languages.best_match(LANGUAGES)
    return result
