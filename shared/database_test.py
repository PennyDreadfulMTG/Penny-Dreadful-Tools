from unittest.mock import Mock, patch

import pytest
from MySQLdb import OperationalError

from shared.database import Database, sqlescape, sqllikeescape
from shared.pd_exception import DatabaseException, InvalidArgumentException


def test_execute_reconnects_and_retries_when_server_has_gone_away() -> None:
    db = Database.__new__(Database)
    db.cursor = Mock()
    db.cursor.execute.side_effect = [OperationalError(2006, 'Server has gone away'), 1]
    db.open_transactions = []

    with patch.object(db, 'connect') as connect:
        assert db.execute_with_reconnect('SELECT 1') == (1, [])

    connect.assert_called_once_with()
    assert db.cursor.execute.call_count == 2

def test_execute_does_not_retry_when_server_goes_away_during_transaction() -> None:
    db = Database.__new__(Database)
    db.cursor = Mock()
    db.cursor.execute.side_effect = OperationalError(2006, 'Server has gone away')
    db.open_transactions = ['transaction']

    with patch.object(db, 'connect') as connect, pytest.raises(DatabaseException, match='during open transactions'):
        db.execute_with_reconnect('INSERT INTO example VALUES (1)')

    connect.assert_called_once_with()
    assert db.cursor.execute.call_count == 1
    assert db.open_transactions == []


def test_sqlescape() -> None:
    assert sqlescape("There's an apostrophe.") == "'There''s an apostrophe.'"
    assert sqlescape('a') == "'a'"
    assert sqlescape(6) == 6
    assert sqlescape(6) != '6'
    assert sqlescape(6, force_string=True) == "'6'"
    assert sqlescape(6, force_string=True) != 6
    assert sqlescape('this\\one') == "'this\\\\one'"
    with pytest.raises(InvalidArgumentException):
        sqlescape({})

def test_sqllikeescape() -> None:
    assert sqllikeescape('a') == "'%%a%%'"
    with pytest.raises(InvalidArgumentException):
        sqllikeescape(6)  # type: ignore
    assert sqllikeescape('this\\one') == "'%%this\\\\one%%'"
    assert sqllikeescape('%') == "'%%\\%%%%'"
    with pytest.raises(InvalidArgumentException):
        sqllikeescape({})  # type: ignore
    hard = r'What % _chance_ of a \?'
    assert sqllikeescape(hard) == r"'%%What \%% \_chance\_ of a \\?%%'"
    assert sqllikeescape(hard, fuzzy=True) == r"'%%W%%h%%a%%t%% %%\%%%% %%\_%%c%%h%%a%%n%%c%%e%%\_%% %%o%%f%% %%a%% %%\\%%?%%'"
