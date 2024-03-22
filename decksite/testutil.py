from functools import wraps
from typing import Any, Callable

from decksite import database
from decksite.database import db
from shared import configuration


def with_test_db(test: Callable) -> Callable:
    @wraps(test)
    def wrapper(*args: Any, **kwargs: Any) -> None:
        old_db_name = configuration.get_str('decksite_database')
        db_name = configuration.get_str('decksite_test_database')
        configuration.CONFIG['decksite_database'] = db_name
        db().execute(f'DROP DATABASE IF EXISTS {db_name}')
        db().execute(f'CREATE DATABASE {db_name}')
        db().execute(f'USE {db_name}')
        database.setup()
        test(*args, **kwargs)
        db().execute(f'DROP DATABASE IF EXISTS {db_name}')
        configuration.CONFIG['decksite_database'] = old_db_name
    return wrapper
