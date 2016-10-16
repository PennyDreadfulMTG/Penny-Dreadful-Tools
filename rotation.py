import datetime
import fetcher

def init():
    standard = fetcher.whatsinstandard()
    return [datetime.datetime.strptime(release["enter_date"], "%Y-%m-%dT%H:%M:%S.%fZ") for release in standard]

def last_rotation():
    return max(d for d in  DATES if d < datetime.datetime.now())

def next_rotation():
    return min(d for d in DATES if d > datetime.datetime.now())

DATES = init()
