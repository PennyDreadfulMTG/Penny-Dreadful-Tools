import datetime
import re
from calendar import timegm
from collections import OrderedDict
from typing import Any, Dict, List, Match, Optional, Tuple

import feedparser
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
APAC_SERIES_TZ = pytz.timezone('Asia/Tokyo')
UTC_TZ = pytz.timezone('UTC')
MTGGOLDFISH_TZ = UTC_TZ
CARDHOARDER_TZ = UTC_TZ

FORM_FORMAT = '%Y-%m-%d %H:%M'

# Converts a UTC timestamp (seconds) into a timezone-aware UTC datetime.
def ts2dt(ts: int) -> datetime.datetime:
    return pytz.timezone('UTC').localize(datetime.datetime.utcfromtimestamp(ts))

# Converts a timezone-aware UTC datetime into a UTC timestamp (seconds).
def dt2ts(dt: datetime.datetime) -> int:
    assert dt.tzinfo is not None, 'datetime must be timezone aware.'
    return round(dt.timestamp())

# Converts the given string in the format `format` to a timezone-aware UTC datetime assuming the original string is in timezone `tz`.
def parse(s: str, date_format: str, tz: Any) -> datetime.datetime:
    dt = datetime.datetime.strptime(s, date_format)
    return tz.localize(dt).astimezone(pytz.timezone('UTC'))

def parse_rfc3339(s: str) -> datetime.datetime:
    # pylint: disable=protected-access
    struct = feedparser._parse_date(s)
    return ts2dt(int(timegm(struct)))

def parse_to_ts(s: str, date_format: str, tz: Any) -> int:
    dt = parse(s, date_format, tz)
    return dt2ts(dt)

def timezone(tzid: str) -> datetime.tzinfo:
    return pytz.timezone(tzid)

def now(tz: Any = None) -> datetime.datetime:
    if tz is None:
        tz = datetime.timezone.utc
    return datetime.datetime.now(tz)

def day_of_week(dt: datetime.datetime, tz: Any) -> str:
    return dt.astimezone(tz).strftime('%A')

def form_date(dt: datetime.datetime, tz: Any) -> str:
    return dt.astimezone(tz).strftime(FORM_FORMAT)

def display_date(dt: datetime.datetime, granularity: int = 1) -> str:
    start = now()
    if (start - dt) > datetime.timedelta(365):
        s = '{:%b %Y}'.format(dt.astimezone(WOTC_TZ))
        return replace_day_with_ordinal(s)
    if (start - dt) > datetime.timedelta(28):
        s = '{:%b _%d_}'.format(dt.astimezone(WOTC_TZ))
        return replace_day_with_ordinal(s)
    suffix = 'ago' if start > dt else 'from now'
    diff = round(abs(start - dt).total_seconds())
    if diff == 0:
        return 'just now'
    return '{duration} {suffix}'.format(duration=display_time(diff, granularity), suffix=suffix)

def replace_day_with_ordinal(s: str) -> str:
    return re.sub(r'_(.*)_', day2ordinal, s)

def day2ordinal(m: Match) -> str:
    p = inflect.engine()
    return p.ordinal(int(m.group(1)))

IntervalsType = Dict[str, Tuple[Optional[int], int]]
ResultsType = List[Tuple[int, str]]

def get_intervals() -> IntervalsType:
    intervals: IntervalsType = OrderedDict()
    intervals['weeks'] = (None, 60 * 60 * 24 * 7, 1000)
    intervals['days'] = (7, 60 * 60 * 24, 7)
    intervals['hours'] = (24, 60 * 60, 24)
    intervals['minutes'] = (60, 60, 45)
    intervals['seconds'] = (60, 1, 31)
    return intervals

def display_time(seconds: float, granularity: int = 2) -> str:
    intervals = get_intervals()
    result: ResultsType = []
    seconds = round(seconds) # in case we've been handed a decimal not an int
    if seconds == 0:
        return 'now'
    for unit, details in intervals.items():
        max_units, seconds_per_unit, rounding_threshold = details
        if len(result) < granularity: # We don't want to consider rounding up yet.
            value = seconds // seconds_per_unit # floor preceeding units
        else:
            value = round_value_appropriately(seconds, seconds_per_unit, max_units, rounding_threshold)
            if value == max_units and seconds < (value * seconds_per_unit): # rounding off bumped us up to one of the *preceeding* unit.
                result = round_up_preceeding_unit(result)
                seconds -= value * seconds_per_unit
                value = 0
        if value > 0 or result: # Either we have the first significant value or we're recording each level because we already did.
            result.append((value, unit))
            seconds -= value * seconds_per_unit
    return ', '.join(['{} {}'.format(value, unit.rstrip('s') if value == 1 else unit) for (value, unit) in result[:granularity] if value > 0])

def round_value_appropriately(seconds: float, seconds_per_unit: int, max_units: int, rounding_threshold: int) -> int:
    if not rounding_threshold:
        return round(seconds / seconds_per_unit)
    value = seconds // seconds_per_unit
    if value >= rounding_threshold:
        return max_units
    return value

def round_up_preceeding_unit(result: ResultsType) -> ResultsType:
    intervals = get_intervals()
    # Send the rounding up back up the chain until we find a value that does not need the previous value rounding up.
    for i in range(1, len(result) + 1):
        prev_value, prev_unit = result[-i]
        result[-i] = (prev_value + 1, prev_unit)
        if result[-i][0] < intervals[prev_unit][1]:
            break
        result[-i] = (0, result[-i][1])
    return result
