from unittest import mock

import pytest

from decksite.data import preaggregation
from shared.pd_exception import LockNotAcquiredException


def test_preaggregate_does_not_rebuild_without_the_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    database = mock.Mock()
    database.get_lock.side_effect = LockNotAcquiredException
    monkeypatch.setattr(preaggregation, 'db', lambda: database)

    preaggregation.preaggregate('_example', 'CREATE TABLE _new_example (_ INT)')

    database.execute.assert_not_called()
    database.release_lock.assert_not_called()
