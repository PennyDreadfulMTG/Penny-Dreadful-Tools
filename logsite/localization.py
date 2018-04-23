from flask import request

from . import BABEL

LANGUAGES = [str(locale) for locale in BABEL.list_translations()]

@BABEL.localeselector
def get_locale():
    result = request.accept_languages.best_match(LANGUAGES)
    return result
