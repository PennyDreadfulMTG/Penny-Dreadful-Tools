import datetime

import pytest

from magic import seasons
from shared.pd_exception import DoesNotExistException, InvalidDataException


def set_info(code: str, enter_date_dt: datetime.datetime) -> seasons.SetInfo:
    date = seasons.DateType('', '')
    return seasons.SetInfo(code, code, code, code, date, date, enter_date_dt)


def test_seasons_enum_uptodate() -> None:
    """If this is failing, go append new set codes to seasons.SEASONS.
       This needs to be done every few months.

       This test is purely for futureproofing, and failing it does not mean anything is currently broken"""
    if seasons.next_rotation_ex().code in ['???', None]:
        return
    assert seasons.next_rotation_ex().code in seasons.SEASONS

def test_rotation_info_recalculates_after_supplemental_rotation(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.datetime(2026, 8, 21, tzinfo=datetime.UTC)
    next_rotation = set_info('FULL', now + datetime.timedelta(days=30))
    previous_rotation = set_info('PREV', now - datetime.timedelta(days=30))
    expired_supplemental = set_info('OLD', now - datetime.timedelta(days=8))
    next_supplemental = set_info('NEW', now + datetime.timedelta(days=60))
    info = seasons.RotationInfo(next_rotation, previous_rotation, expired_supplemental, previous_rotation)

    monkeypatch.setattr(seasons.dtutil, 'now', lambda: now)
    monkeypatch.setattr(seasons, 'calc_next', lambda supplemental: next_supplemental if supplemental else next_rotation)
    monkeypatch.setattr(seasons, 'calc_prev', lambda supplemental: expired_supplemental if supplemental else previous_rotation)

    info.validate()

    assert info.next_supplemental == next_supplemental

def test_season_id() -> None:
    assert seasons.season_id(1) == 1
    with pytest.raises(DoesNotExistException):
        seasons.season_id(999)
    with pytest.raises(DoesNotExistException):
        seasons.season_id('ISD')
    with pytest.raises(DoesNotExistException):
        seasons.season_id(-999)
    with pytest.raises(DoesNotExistException):
        seasons.season_id(-10)
    assert seasons.season_id('HOU') == 5
    assert seasons.season_id('hou') == 5
    assert seasons.season_id('ALL') == 'all'
    assert seasons.season_id('all') == 'all'

def test_season_num_rejects_unknown_code() -> None:
    with pytest.raises(InvalidDataException, match='not-a-season'):
        seasons.season_num('not-a-season')

def test_season_code() -> None:
    assert seasons.season_code(1) == 'EMN'
    with pytest.raises(DoesNotExistException):
        seasons.season_code(999)
    with pytest.raises(DoesNotExistException):
        seasons.season_code('ISD')
    assert seasons.season_code('HOU') == 'HOU'
    assert seasons.season_code('hou') == 'HOU'
    assert seasons.season_code('ALL') == 'ALL'
    assert seasons.season_code('all') == 'ALL'
    with pytest.raises(DoesNotExistException):
        seasons.season_code(-1)

def test_season_name() -> None:
    assert seasons.season_name(1) == 'Season 1'
    with pytest.raises(DoesNotExistException):
        seasons.season_name(999)
    with pytest.raises(DoesNotExistException):
        assert seasons.season_name('ISD')
    assert seasons.season_name('EMN') == 'Season 1'
    assert seasons.season_name('emn') == 'Season 1'
    assert seasons.season_name('HOU') == 'Season 5'
    assert seasons.season_name('hou') == 'Season 5'
    assert seasons.season_name('ALL') == 'All Time'
    assert seasons.season_name('all') == 'All Time'
    assert seasons.season_name(0) == 'All Time'
