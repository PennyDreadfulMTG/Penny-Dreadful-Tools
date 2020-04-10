import datetime

from pytz import timezone

from shared import dtutil


def test_ts2dt() -> None:
    epoch_seconds = 0
    dt = dtutil.ts2dt(epoch_seconds)
    assert '{:%Y-%m-%d %H:%M:%S %z}'.format(dt) == '1970-01-01 00:00:00 +0000'
    now = datetime.datetime.now(datetime.timezone.utc)
    dt = dtutil.ts2dt(int(now.timestamp()))
    assert '{:%Y-%m-%d %H:%M:%S %z}'.format(dt) == '{:%Y-%m-%d %H:%M:%S %z}'.format(now)

def test_dt2ts() -> None:
    dt = timezone('UTC').localize(datetime.datetime.utcfromtimestamp(0))
    assert dtutil.dt2ts(dt) == 0
    now = datetime.datetime.now(datetime.timezone.utc)
    now_ts = round(now.timestamp())
    assert dtutil.dt2ts(now) == now_ts

def test_end_to_end() -> None:
    epoch_seconds = 0
    dt = dtutil.ts2dt(epoch_seconds)
    assert epoch_seconds == dtutil.dt2ts(dt)

def test_parse() -> None:
    s = '1970-01-01 00:00:00'
    dt = dtutil.parse(s, '%Y-%m-%d %H:%M:%S', timezone('UTC'))
    assert '{:%Y-%m-%d %H:%M:%S %z}'.format(dt) == '1970-01-01 00:00:00 +0000'
    s = '2016-01-01 00:00:00'
    dt = dtutil.parse(s, '%Y-%m-%d %H:%M:%S', timezone('UTC'))
    assert '{:%Y-%m-%d %H:%M:%S %z}'.format(dt) == '2016-01-01 00:00:00 +0000'
    dt = dtutil.parse(s, '%Y-%m-%d %H:%M:%S', timezone('America/Los_Angeles'))
    assert '{:%Y-%m-%d %H:%M:%S %z}'.format(dt) == '2016-01-01 08:00:00 +0000'

def test_parse_rfc3339() -> None:
    s = '2002-10-02T10:00:00-05:00'
    dt = dtutil.parse_rfc3339(s)
    assert '{:%Y-%m-%d %H:%M:%S %z}'.format(dt) == '2002-10-02 15:00:00 +0000'
    s = '2002-10-02T15:00:00Z'
    dt = dtutil.parse_rfc3339(s)
    assert '{:%Y-%m-%d %H:%M:%S %z}'.format(dt) == '2002-10-02 15:00:00 +0000'
    s = '2002-10-02T15:00:00.05Z'
    dt = dtutil.parse_rfc3339(s)
    assert '{:%Y-%m-%d %H:%M:%S %z}'.format(dt) == '2002-10-02 15:00:00 +0000'

def test_parse_to_ts() -> None:
    s = '1970-01-01 00:00:00'
    assert dtutil.parse_to_ts(s, '%Y-%m-%d %H:%M:%S', timezone('UTC')) == 0
    s = '1970-01-01 00:01:59'
    assert dtutil.parse_to_ts(s, '%Y-%m-%d %H:%M:%S', timezone('UTC')) == 119
    assert str(dtutil.parse_to_ts(s, '%Y-%m-%d %H:%M:%S', timezone('UTC'))) == '119'

def test_now() -> None:
    then = dtutil.parse('2016-01-01', '%Y-%m-%d', dtutil.WOTC_TZ)
    now = dtutil.now()
    assert (now - then).total_seconds() > 0

def test_display_date() -> None:
    dt = dtutil.parse('2008-03-29', '%Y-%m-%d', dtutil.WOTC_TZ)
    assert dtutil.display_date(dt) == 'Mar 2008'
    dt = dtutil.parse('2008-03-29 02:00', '%Y-%m-%d %H:%M', timezone('UTC'))
    assert dtutil.display_date(dt) == 'Mar 2008'
    dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=10)
    assert dtutil.display_date(dt).find('seconds ago') >= 0
    dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=72)
    assert dtutil.display_date(dt).find('days') >= 0
    assert dtutil.display_date(dt).find('from now') >= 0
    assert dtutil.display_date(dt).find('ago') == -1
    dt = datetime.datetime.now(datetime.timezone.utc)
    assert dtutil.display_date(dt).find('just now') >= 0
    assert dtutil.display_date(dt).find('from now') == -1
    dt = datetime.datetime.now(dtutil.WOTC_TZ) + datetime.timedelta(days=28, hours=15, minutes=35)
    assert dtutil.display_date(dt) == '4 weeks from now'
    dt = datetime.datetime.now(dtutil.WOTC_TZ) + datetime.timedelta(days=6)
    assert dtutil.display_date(dt) == '6 days from now'

def test_rounding() -> None:
    assert dtutil.display_time(121, granularity=1) == '2 minutes'
    assert dtutil.display_time(121, granularity=2) == '2 minutes, 1 second'
    assert dtutil.display_time(121, granularity=3) == '2 minutes, 1 second'
    assert dtutil.display_time(159, granularity=1) == '3 minutes'
    assert dtutil.display_time(91, granularity=1) == '2 minutes'
    assert dtutil.display_time(6900, granularity=2) == '1 hour, 55 minutes'
    assert dtutil.display_time(345610, granularity=4) == '4 days, 10 seconds'
    assert dtutil.display_time(4860) == '1 hour, 21 minutes'
    assert dtutil.display_time(86400.0) == '1 day'
    assert dtutil.display_time(0, 2) == 'now'
    assert dtutil.display_time(0.4, 2) == 'now'
    assert dtutil.display_time(0.9, 2) == '1 second'

def test_round_up_preceeding_unit() -> None:
    results = [(1, 'hours'), (59, 'minutes'), (59, 'seconds')]
    dtutil.round_up_preceeding_unit(results)
    assert results == [(2, 'hours'), (0, 'minutes'), (0, 'seconds')]

def test_display_time() -> None:
    assert dtutil.display_time(60 * 60 * 2 - 1 * 60) == '1 hour, 59 minutes'
    assert dtutil.display_time(60 * 60 * 2 + 1 * 60) == '2 hours, 1 minute'
    assert dtutil.display_time(60 * 60 * 2 - 1) == '2 hours'
    assert dtutil.display_time(60 * 60 * 2 + 1) == '2 hours'
    assert dtutil.display_time(60 * 60 * 2 - 1, 1) == '2 hours'
    assert dtutil.display_time(60 * 60 * 2 + 1, 1) == '2 hours'
    assert dtutil.display_time((24 * 60 * 60 * 3) + (60 * 60 * 2) + (60 * 59)) == '3 days, 3 hours'
    assert dtutil.display_time((24 * 60 * 60 * 3) + (60 * 60 * 2) + (60 * 29)) == '3 days, 2 hours'
    assert dtutil.display_time(2417366.810318) == '3 weeks, 6 days'

def test_round_value_appropriately() -> None:
    assert dtutil.round_value_appropriately(59, 1, 60, 30) == 60
    assert dtutil.round_value_appropriately(29, 1, 60, 30) == 29
    assert dtutil.round_value_appropriately(6 * 24 * 60 * 60, 24 * 60 * 60, 7, 7) == 6
    assert dtutil.round_value_appropriately(7 * 24 * 60 * 60, 24 * 60 * 60, 7, 7) == 7
