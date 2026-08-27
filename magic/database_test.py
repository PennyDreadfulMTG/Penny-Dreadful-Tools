import datetime

import pytest

from magic import database


def test_card_information_at_maximum_age_is_not_stale(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.datetime(2026, 8, 21, tzinfo=datetime.UTC)
    monkeypatch.setattr(database.dtutil, 'now', lambda: now)
    monkeypatch.setattr(database, 'last_updated', lambda: now - database.MAX_CARD_INFORMATION_AGE)

    assert database.stale_card_information_age() is None

def test_card_information_older_than_maximum_age_is_stale(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.datetime(2026, 8, 21, tzinfo=datetime.UTC)
    age = datetime.timedelta(days=4)
    monkeypatch.setattr(database.dtutil, 'now', lambda: now)
    monkeypatch.setattr(database, 'last_updated', lambda: now - age)

    assert database.stale_card_information_age() == age
