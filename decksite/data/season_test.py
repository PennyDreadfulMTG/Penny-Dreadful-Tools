import pytest

from decksite.data import season
from shared import dtutil
from shared.pd_exception import InvalidDataException


def test_get_season_id() -> None:
    # These tests check pretty old dates because the test db only has up to season 7.
    dt = dtutil.parse('2017-09-12 00:00:00', '%Y-%m-%d %H:%M:%S', dtutil.WOTC_TZ)
    assert season.get_season_id(dt) == 5
    dt = dtutil.parse('2016-11-01 00:00:00', '%Y-%m-%d %H:%M:%S', dtutil.WOTC_TZ)
    assert season.get_season_id(dt) == 2
    with pytest.raises(InvalidDataException):
        dt = dtutil.parse('1990-01-01 00:00:00', '%Y-%m-%d %H:%M:%S', dtutil.WOTC_TZ)
        season.get_season_id(dt)
