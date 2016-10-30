from magic import fetcher
from shared import dtutil

def init():
    standard = fetcher.whatsinstandard()
    return [parse_rotation_date(release["enter_date"]) for release in standard]

def last_rotation():
    return max(d for d in  DATES if d < dtutil.now())

def next_rotation():
    return min(d for d in DATES if d > dtutil.now())

def parse_rotation_date(s):
    return dtutil.parse(s, "%Y-%m-%dT%H:%M:%S.%fZ", dtutil.WOTC_TZ)

DATES = init()
