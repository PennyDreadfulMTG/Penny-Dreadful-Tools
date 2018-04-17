import datetime
from typing import Dict, List, Union, cast

from magic import fetcher
from shared import dtutil

SetInfo = Dict[str, Union[str, datetime.datetime]] #pylint: disable=invalid-name

def init() -> List[SetInfo]:
    info = fetcher.whatsinstandard()
    if info['deprecated']:
        print('Current whatsinstandard API version is DEPRECATED.')
    set_info = cast(List[SetInfo], info['sets'])
    return [parse_rotation_date(release) for release in set_info]

def last_rotation():
    return last_rotation_ex()['enter_date']

def next_rotation():
    return next_rotation_ex()['enter_date']

def last_rotation_ex():
    return max([s for s in sets() if s['enter_date'] < dtutil.now()], key=lambda s: s['enter_date'])

def next_rotation_ex():
    return min([s for s in sets() if s['enter_date'] > dtutil.now()], key=lambda s: s['enter_date'])

def next_supplemental():
    last = last_rotation() + datetime.timedelta(weeks=3)
    if last > dtutil.now():
        return last
    return next_rotation() + datetime.timedelta(weeks=3)

def parse_rotation_date(setinfo: SetInfo) -> SetInfo:
    setinfo['enter_date'] = dtutil.parse(cast(str, setinfo['enter_date']), '%Y-%m-%dT%H:%M:%S.%fZ', dtutil.WOTC_TZ)
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

def text() -> str:
    full = next_rotation()
    supplemental = next_supplemental()
    now = dtutil.now()
    sdiff = supplemental - now
    diff = full - now
    if sdiff < diff:
        return "The supplemental rotation is in {sdiff} (The next full rotation is in {diff})".format(diff=dtutil.display_time(diff.total_seconds()), sdiff=dtutil.display_time(sdiff.total_seconds()))
    return "The next rotation is in {diff}".format(diff=dtutil.display_time(diff.total_seconds()))

__SETS: List[SetInfo] = []
def sets():
    if not __SETS:
        __SETS.extend(init())
    return __SETS
