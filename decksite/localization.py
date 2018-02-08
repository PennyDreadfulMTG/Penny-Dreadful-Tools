import re
from typing import Sequence

from flask import request, session

from . import BABEL as babel

LANGUAGES = [str(locale) for locale in babel.list_translations()]
SPLIT_REGEX = re.compile(r'^(.*)\[\[(.*)\]\](.*)$')

@babel.localeselector
def get_locale() -> str:
    result = request.args.get('locale', None)
    if result:
        session['locale'] = result
        return result
    result = session.get('locale', None)
    if not result:
        result = request.accept_languages.best_match(LANGUAGES)
    return result

def split_link(para: str) -> Sequence[str]:
    return SPLIT_REGEX.match(para).groups()
