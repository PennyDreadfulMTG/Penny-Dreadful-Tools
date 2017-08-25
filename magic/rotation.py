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


def parse_rotation_date(setinfo):
    setinfo['enter_date'] = dtutil.parse(setinfo['enter_date'], '%Y-%m-%dT%H:%M:%S.%fZ', dtutil.WOTC_TZ)
    return setinfo

SETS = init()
