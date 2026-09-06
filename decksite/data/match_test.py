import datetime
from unittest.mock import call, patch

import pytest

from decksite.data import match
from shared.database import Database


def test_insert_match_rolls_back_on_error() -> None:
    database = Database.__new__(Database)
    database.open_transactions = []

    with (
        patch.object(database, 'execute') as execute,
        patch.object(database, 'insert', return_value=123),
        patch.object(match, 'db', return_value=database),
        patch.object(match, 'update_cache', side_effect=RuntimeError('cache update failed')),
        pytest.raises(RuntimeError, match='cache update failed'),
    ):
        match.insert_match(datetime.datetime.now(datetime.UTC), 1, 2, 2, 1)

    assert database.open_transactions == []
    assert execute.call_args_list == [
        call('BEGIN'),
        call('ROLLBACK'),
    ]
