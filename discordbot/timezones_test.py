import pytest

from discordbot import geonames, timezones


def test_time_treats_short_city_as_a_location(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(geonames, 'find', lambda query: geonames.Place('Lima', 'PE', 'LMA', 'America/Lima') if query == 'Lima' else None)
    monkeypatch.setattr(timezones, 'current_time', lambda _timezone, _twentyfour: '12:34 PM')

    assert timezones.time('Lima', False) == {'12:34 PM': ['Lima, PE']}


@pytest.mark.parametrize('query', ['ninja', 'television'])
def test_time_rejects_words_that_are_not_populated_places(monkeypatch: pytest.MonkeyPatch, query: str) -> None:
    monkeypatch.setattr(geonames, 'find', lambda _query: None)

    with pytest.raises(timezones.TooFewItemsException):
        timezones.time(query, False)


def test_time_accepts_iana_timezone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timezones, 'current_time', lambda _timezone, _twentyfour: '12:34 PM')

    assert timezones.time('Australia/Sydney', False) == {'12:34 PM': ['Australia/Sydney']}


def test_time_accepts_utc_offset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timezones, 'current_time', lambda timezone, _twentyfour: str(timezone.utcoffset(None)))

    assert timezones.time('UTC+10', False) == {'10:00:00': ['UTC+10']}


def test_time_preserves_ambiguous_abbreviations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timezones, 'current_time', lambda _timezone, _twentyfour: '12:34 PM')

    result = timezones.time('AEST', False)

    assert 'Australia/Brisbane' in result['12:34 PM']
