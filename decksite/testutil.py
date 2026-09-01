import os
from collections.abc import Callable
from functools import wraps
from typing import Any

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
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        with open(schema_path) as f:
            sql = f.read()
        for stmt in sql.split(';'):
            if stmt.strip():
                db().execute(stmt)
        test(*args, **kwargs)
        db().execute(f'DROP DATABASE IF EXISTS {db_name}')
        configuration.CONFIG['decksite_database'] = old_db_name
    return wrapper
