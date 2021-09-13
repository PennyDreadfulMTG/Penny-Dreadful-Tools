from decksite.data import season
from shared import dtutil
from shared.pd_exception import InvalidDataException


def test_load_season_id() -> None:
    dt = dtutil.parse('2021-09-12 00:00:00', '%Y-%m-%d %H:%M:%S', dtutil.WOTC_TZ)
    assert season.get_season_id(dt) == 21
    dt = dtutil.parse('2016-11-01 00:00:00', '%Y-%m-%d %H:%M:%S', dtutil.WOTC_TZ)
    assert season.get_season_id(dt) == 2
    found = False
    try:
        dt = dtutil.parse('1990-01-01 00:00:00', '%Y-%m-%d %H:%M:%S', dtutil.WOTC_TZ)
        season.get_season_id(dt)
    except InvalidDataException:
        found = True
    assert found
