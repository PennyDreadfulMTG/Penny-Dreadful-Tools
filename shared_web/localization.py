import re
from typing import List, Optional

from flask import request, session
from flask_babel import Babel

LANGUAGES: List[str] = []
SPLIT_REGEX = re.compile(r'^(.*)\[\[(.*)\]\](.*)$')
VALID_LOCALE = re.compile(r'^[a-zA-Z_]+$')

def get_locale() -> Optional[str]:
    result = check_sql_injection(request.args.get('locale', None))
    if result:
        session['locale'] = result
        return result
    result = session.get('locale', None)
    if not result:
        result = request.accept_languages.best_match(LANGUAGES)
    return result

def check_sql_injection(locale: Optional[str]) -> Optional[str]:
    if locale is None:
        return None
    if not VALID_LOCALE.match(locale):
        return None
    return locale

def init(babel: Babel) -> None:
    LANGUAGES.extend([str(locale) for locale in babel.list_translations()])
    babel.localeselector(get_locale)
