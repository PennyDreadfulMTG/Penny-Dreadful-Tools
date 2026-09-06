import re

from flask import request, session
from flask_babel import Babel

LANGUAGES: list[str] = []
SPLIT_REGEX = re.compile(r'^(.*)\[\[(.*)\]\](.*)$')

def get_locale() -> str | None:
    result = session.get('locale', None)
    if result in LANGUAGES:
        return result
    session.pop('locale', None)
    return request.accept_languages.best_match(LANGUAGES)

def init(babel: Babel) -> None:
    LANGUAGES[:] = [str(locale) for locale in babel.list_translations()]
