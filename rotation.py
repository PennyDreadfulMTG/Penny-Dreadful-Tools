import datetime
from dateutil import tz
import fetcher

def init():
    standard = fetcher.whatsinstandard()
    return [parse_rotation_date(release["enter_date"]) for release in standard]

def last_rotation():
    return max(d for d in  DATES if d < now())

def next_rotation():
    return min(d for d in DATES if d > now())

def parse_rotation_date(s):
    return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=tz.gettz('America/Los_Angeles'))

def now():
    return datetime.datetime.now().replace(tzinfo=tz.tzlocal())

DATES = init()
