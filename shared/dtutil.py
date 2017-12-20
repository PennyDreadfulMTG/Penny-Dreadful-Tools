import datetime
import re

import inflect
import pytz

# All dates should be stored as a UTC timestamp (seconds).
# All dates should be manipulated in memory as a timezone-aware UTC datetime.
# This lib means you don't have to know how to do that in python.
# Call ts2dt on anything you pull out of the database immediately after you retrieve it.
# Call dt2ts on anything you put into the database immediately before putting it in.
# Parse any dates you get as strings using parse.

GATHERLING_TZ = pytz.timezone('America/New_York')
WOTC_TZ = pytz.timezone('America/Los_Angeles')
UTC_TZ = pytz.timezone('UTC')
MTGGOLDFISH_TZ = UTC_TZ
CARDHOARDER_TZ = UTC_TZ

# Converts a UTC timestamp (seconds) into a timezone-aware UTC datetime.
def ts2dt(ts):
    return pytz.timezone('UTC').localize(datetime.datetime.utcfromtimestamp(ts))

# Converts a timezone-aware UTC datetime into a UTC timestamp (seconds).
def dt2ts(dt):
    return dt.timestamp()

# Converts the given string in the format `format` to a timezone-aware UTC datetime assuming the original string is in timezone `tz`.
def parse(s, date_format, tz):
    dt = datetime.datetime.strptime(s, date_format)
    return tz.localize(dt).astimezone(pytz.timezone('UTC'))

def parse_to_ts(s, date_format, tz):
    dt = parse(s, date_format, tz)
    return dt2ts(dt)

def timezone(tzid):
    return pytz.timezone(tzid)

def now(tz=None):
    if tz is None:
        tz = datetime.timezone.utc
    return datetime.datetime.now(tz)

def display_date(dt, granularity=1):
    start = now()
    if (start - dt) > datetime.timedelta(365):
        s = '{:%b %Y}'.format(dt.astimezone(WOTC_TZ))
        return replace_day_with_ordinal(s)
    if (start - dt) > datetime.timedelta(28):
        s = '{:%b _%d_}'.format(dt.astimezone(WOTC_TZ))
        return replace_day_with_ordinal(s)
    else:
        suffix = 'ago' if start > dt else 'from now'
        diff = round(abs(start - dt).total_seconds())
        if diff == 0:
            return 'just now'
        return '{duration} {suffix}'.format(duration=display_time(diff, granularity), suffix=suffix)

def replace_day_with_ordinal(s):
    return re.sub(r'_(.*)_', day2ordinal, s)

def day2ordinal(m):
    p = inflect.engine()
    return p.ordinal(int(m.group(1)))

def display_time(seconds, granularity=2):
    intervals = (
        ('weeks', 60 * 60 * 24 * 7),
        ('days', 60 * 60 * 24),
        ('hours', 60 * 60),
        ('minutes', 60),
        ('seconds', 1)
    )
    result = []
    seconds = round(seconds) # in case we've been handed a decimal not an int
    if seconds == 0:
        return 'now'
    for unit, count in intervals:
        if len(result) < granularity - 1:
            value = seconds // count # floor preceeding units
        else:
            value = round(seconds / count) # round off last unit
            if value == count and unit != 'seconds': # rounding off bumped us up to one of the *preceeding* unit.
                prev_value, prev_unit = result[-1]
                result[-1] = (prev_value + 1, prev_unit)
                seconds -= value * count
                value = 0
        if value > 0 or len(result):
            result.append((value, unit))
            seconds -= value * count
    return ', '.join(['{} {}'.format(value, unit.rstrip('s') if value == 1 else unit) for (value, unit) in result[:granularity] if value > 0])
