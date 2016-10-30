import datetime

from dateutil import tz

# All dates should be stored as a UTC timestamp (seconds).
# All dates should be manipulated in memory as a timezone-aware UTC datetime.
# This lib means you don't have to know how to do that in pyton.
# Call ts2dt on anything you pull out of the database immediately after you retrieve it.
# Call dt2ts on anything you put into the database immediately before putting it in.
# Parse any dates you get as strings using parse.

GATHERLING_TZ = tz.gettz('America/New_York')
WOTC_TZ = tz.gettz('America/Los_Angeles')

# Converts a UTC timestamp (seconds) into a timezone-aware UTC datetime.
def ts2dt(ts):
    return datetime.datetime.fromtimestamp(ts).replace(tzinfo=tz.tzlocal()).astimezone(tz=tz.tzutc())

# Converts a timezone-aware UTC datetime into a UTC timestamp (seconds).
def dt2ts(dt):
  return dt.replace(tzinfo=tz.tzutc()).timestamp()

# Converts the given string in the format `format` to a timezone-aware UTC datetime assuming the original string is in timezone `tz`.
def parse(s, date_format, timezone):
    dt = datetime.datetime.strptime(s, date_format)
    return dt.replace(tzinfo=timezone).astimezone(tz=tz.tzutc())

def parse_to_ts(s, date_format, timezone):
    dt = parse(s, date_format, timezone)
    return dt2ts(dt)

def now():
    return datetime.datetime.now().replace(tzinfo=tz.tzlocal()).astimezone(tz.tzutc())

def display_date(dt, granularity=1):
    start = now()
    if (start - dt) > datetime.timedelta(365):
        return '{:%b %d, %Y}'.format(dt)
    if (start - dt) > datetime.timedelta(28):
        return '{:%b %d}'.format(dt)
    else:
        diff = start - dt
        return '{duration} ago'.format(duration=display_time(diff.total_seconds(), granularity))

def display_time(seconds, granularity=2):
    intervals = (
        ('weeks', 60 * 60 * 24 * 7),
        ('days', 60 * 60 * 24),
        ('hours', 60 * 60),
        ('minutes', 60),
        ('seconds', 1)
    )
    result = []
    for name, count in intervals:
        value = seconds // count
        if value:
            seconds -= value * count
            if value == 1:
                name = name.rstrip('s')
            result.append("{} {}".format(round(value), name))
        else:
            # Add a blank if we're in the middle of other values
            if len(result) > 0:
                result.append(None)
    return ', '.join([x for x in result[:granularity] if x is not None])
