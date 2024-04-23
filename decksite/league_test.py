from datetime import timedelta

import pytest

from decksite import league
from shared import dtutil
from shared.pd_exception import InvalidArgumentException


def test_determine_end_of_league() -> None:
    next_rotation = dtutil.parse('2018-02-01 00:00:00', '%Y-%m-%d %H:%M:%S', dtutil.WOTC_TZ)

    start_date = dtutil.parse('2017-11-01 00:00:00', '%Y-%m-%d %H:%M:%S', dtutil.WOTC_TZ)
    end_date = league.determine_end_of_league(start_date, next_rotation)
    assert dtutil.dt2ts(end_date) == 1512115199

    start_date = dtutil.parse('2017-10-31 11:59:59.999', '%Y-%m-%d %H:%M:%S.%f', dtutil.WOTC_TZ)
    end_date = league.determine_end_of_league(start_date, next_rotation)
    assert dtutil.dt2ts(end_date) == 1512115199

    next_rotation = dtutil.parse('2018-07-13 00:00:00', '%Y-%m-%d %H:%M:%S', dtutil.WOTC_TZ)

    start_date = dtutil.parse('2018-05-31 11:04:15', '%Y-%m-%d %H:%M:%S', dtutil.WOTC_TZ)
    end_date = league.determine_end_of_league(start_date, next_rotation)
    assert dtutil.dt2ts(end_date) == dtutil.dt2ts(next_rotation) - 1

    next_rotation = dtutil.parse('2018-10-10 00:00:00', '%Y-%m-%d %H:%M:%S', dtutil.WOTC_TZ)

    start_date = dtutil.parse('2018-08-01 00:00:00', '%Y-%m-%d %H:%M:%S', dtutil.WOTC_TZ)
    end_date = league.determine_end_of_league(start_date, next_rotation)
    assert end_date == dtutil.parse('2018-08-31 23:59:59', '%Y-%m-%d %H:%M:%S', dtutil.WOTC_TZ)

    start_date = dtutil.parse('2018-07-13 00:00:00', '%Y-%m-%d %H:%M:%S', dtutil.WOTC_TZ)
    end_date = league.determine_end_of_league(start_date, next_rotation)
    assert end_date == dtutil.parse('2018-07-31 23:59:59', '%Y-%m-%d %H:%M:%S', dtutil.WOTC_TZ)

    # We won't make a 0 seconds league, see #9216.
    next_rotation = dtutil.parse('2021-10-01 00:00:00',  '%Y-%m-%d %H:%M:%S', dtutil.WOTC_TZ)
    with pytest.raises(InvalidArgumentException):
        league.determine_end_of_league(next_rotation, next_rotation)

    # But we will reluctantly make a league that is one day long if that's what's seemingly called for.
    end_date = league.determine_end_of_league(next_rotation, next_rotation + timedelta(days=1))
    assert end_date == next_rotation + timedelta(days=1) - timedelta(seconds=1)


def test_determine_league_name() -> None:
    start_date = dtutil.parse('2017-11-01 00:00:00', '%Y-%m-%d %H:%M:%S', dtutil.WOTC_TZ)
    end_date = dtutil.parse('2017-11-30 23:59:59.999', '%Y-%m-%d %H:%M:%S.%f', dtutil.WOTC_TZ)
    assert league.determine_league_name(start_date, end_date) == 'League November 2017'
    start_date = dtutil.parse('2017-09-01 00:00:00', '%Y-%m-%d %H:%M:%S', dtutil.WOTC_TZ)
    end_date = dtutil.parse('2017-10-10 23:59:59.999', '%Y-%m-%d %H:%M:%S.%f', dtutil.WOTC_TZ)
    assert league.determine_league_name(start_date, end_date) == 'League September 2017'
    start_date = dtutil.parse('2022-09-16 00:00:00', '%Y-%m-%d %H:%M:%S', dtutil.WOTC_TZ)
    end_date = dtutil.parse('2022-10-31 23:59:59.999', '%Y-%m-%d %H:%M:%S.%f', dtutil.WOTC_TZ)
    assert league.determine_league_name(start_date, end_date) == 'League October 2022'
