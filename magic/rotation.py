import datetime

from magic import fetcher
from shared import dtutil


def init():
    info = fetcher.whatsinstandard()
    if info['deprecated']:
        print('Current whatsinstandard API version is DEPRECATED.')
    sets = info['sets']
    return [parse_rotation_date(release) for release in sets]

def last_rotation():
    return last_rotation_ex()['enter_date']

def next_rotation():
    return next_rotation_ex()['enter_date']

def last_rotation_ex():
    return max([s for s in SETS if s['enter_date'] < dtutil.now()], key=lambda s: s['enter_date'])

def next_rotation_ex():
    return min([s for s in SETS if s['enter_date'] > dtutil.now()], key=lambda s: s['enter_date'])

def next_supplemental():
    last = last_rotation() + datetime.timedelta(weeks=3)
    if last > dtutil.now():
        return last
    return next_rotation() + datetime.timedelta(weeks=3)

def parse_rotation_date(setinfo):
    setinfo['enter_date'] = dtutil.parse(setinfo['enter_date'], '%Y-%m-%dT%H:%M:%S.%fZ', dtutil.WOTC_TZ)
    return setinfo

def interesting(playability, c, speculation=True, new=True):
    if new and len({k: v for (k, v) in c['legalities'].items() if 'Penny Dreadful' in k}) == (0 if speculation else 1):
        return 'new'
    p = playability.get(c.name, 0)
    if p > 0.1:
        return 'heavily-played'
    elif p > 0.01:
        return 'moderately-played'
    return None

SETS = init()
