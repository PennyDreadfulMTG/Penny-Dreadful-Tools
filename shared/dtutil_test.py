import datetime
import time

from dateutil import tz

from shared import dtutil

def test_ts2dt():
    epoch_seconds = 0
    dt = dtutil.ts2dt(epoch_seconds)
    assert '{:%Y-%m-%d %H:%M:%S %z}'.format(dt) == '1970-01-01 00:00:00 +0000'
    now_seconds = time.time()
    dt = dtutil.ts2dt(now_seconds)
    assert '{:%Y-%m-%d %H:%M:%S %z}'.format(dt) == '{:%Y-%m-%d %H:%M:%S %z}'.format(datetime.datetime.utcnow().replace(tzinfo=tz.tzutc()))

def test_dt2ts():
    dt = datetime.datetime.utcfromtimestamp(0).replace(tzinfo=tz.tzutc())
    assert dtutil.dt2ts(dt) == 0
    now = datetime.datetime.utcnow().replace(tzinfo=tz.tzutc())
    now_ts = now.timestamp()
    assert dtutil.dt2ts(now) == now_ts

def test_end_to_end():
    epoch_seconds = 0
    dt = dtutil.ts2dt(epoch_seconds)
    assert epoch_seconds == dtutil.dt2ts(dt)

def test_parse():
    s = '1970-01-01 00:00:00'
    dt = dtutil.parse(s, '%Y-%m-%d %H:%M:%S', tz.tzutc())
    print(dt)
    assert '{:%Y-%m-%d %H:%M:%S %z}'.format(dt) == '1970-01-01 00:00:00 +0000'
    s = '2016-01-01 00:00:00'
    dt = dtutil.parse(s, '%Y-%m-%d %H:%M:%S', tz.tzutc())
    assert '{:%Y-%m-%d %H:%M:%S %z}'.format(dt) == '2016-01-01 00:00:00 +0000'
    dt = dtutil.parse(s, '%Y-%m-%d %H:%M:%S', tz.gettz('America/Los_Angeles'))
    assert '{:%Y-%m-%d %H:%M:%S %z}'.format(dt) == '2016-01-01 08:00:00 +0000'

def test_parse_to_ts():
    s = '1970-01-01 00:00:00'
    assert dtutil.parse_to_ts(s, '%Y-%m-%d %H:%M:%S', tz.tzutc()) == 0

def test_now():
    then = dtutil.parse('2016-01-01', '%Y-%m-%d', dtutil.WOTC_TZ)
    now = dtutil.now()
    assert (now - then).total_seconds() > 0

def test_display_date():
    dt = dtutil.parse('2008-03-29', '%Y-%m-%d', tz.tzlocal())
    assert dtutil.display_date(dt) == 'Mar 29, 2008'
    dt = datetime.datetime.now().replace(tzinfo=tz.tzlocal()) - datetime.timedelta(seconds=10)
    assert dtutil.display_date(dt).find('seconds') >= 0
