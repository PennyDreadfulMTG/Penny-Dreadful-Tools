import datetime
import glob
import os
from typing import Dict, List, Optional, Union, cast

from mypy_extensions import TypedDict

from magic import fetcher
from magic.models.card import Card
from shared import configuration, dtutil
from shared.pd_exception import DoesNotExistException, InvalidDataException

SetInfoType = TypedDict('SetInfoType', {
    'name': str,
    'block': Optional[str],
    'code': str,
    'mtgo_code': str,
    'enter_date': str,
    'exit_date': str,
    'rough_exit_date': str,
    'enter_date_dt': datetime.datetime,
    })

SEASONS = [
    'EMN', 'KLD', # 2016
    'AER', 'AKH', 'HOU', 'XLN', # 2017
    'RIX', 'DOM', 'M19', 'GRN', #2018
    'RNA', # 2019
    ]

def init() -> List[SetInfoType]:
    info = fetcher.whatsinstandard()
    if info['deprecated']:
        print('Current whatsinstandard API version is DEPRECATED.')
    set_info = cast(List[SetInfoType], info['sets'])
    return [postprocess(release) for release in set_info]

def current_season_code() -> str:
    return last_rotation_ex()['code']

def current_season_num() -> int:
    return season_num(current_season_code())

def season_num(code_to_look_for: str) -> int:
    n = 0
    for code in SEASONS:
        n += 1
        if code == code_to_look_for:
            return n
    raise InvalidDataException('I did not find the current season code (`{code}`) in the list of seasons ({seasons}) and I am confused.'.format(code=code_to_look_for, seasons=','.join(SEASONS)))

def last_rotation() -> datetime.datetime:
    return last_rotation_ex()['enter_date_dt']

def next_rotation() -> datetime.datetime:
    return next_rotation_ex()['enter_date_dt']

def last_rotation_ex() -> SetInfoType:
    return max([s for s in sets() if s['enter_date_dt'] < dtutil.now()], key=lambda s: s['enter_date_dt'])

def next_rotation_ex() -> SetInfoType:
    return min([s for s in sets() if s['enter_date_dt'] > dtutil.now()], key=lambda s: s['enter_date_dt'])

def next_supplemental() -> datetime.datetime:
    last = last_rotation() + datetime.timedelta(weeks=3)
    if last > dtutil.now():
        return last
    return next_rotation() + datetime.timedelta(weeks=3)

def this_supplemental() -> datetime.datetime:
    return last_rotation() + datetime.timedelta(weeks=3)

def postprocess(setinfo: SetInfoType) -> SetInfoType:
    setinfo['enter_date_dt'] = dtutil.parse(setinfo['enter_date'], '%Y-%m-%dT%H:%M:%S.%f', dtutil.WOTC_TZ)
    if setinfo['code'] == 'DOM': # !quality
        setinfo['mtgo_code'] = 'DAR'
    else:
        setinfo['mtgo_code'] = setinfo['code']
    return setinfo

def interesting(playability: Dict[str, float], c: Card, speculation: bool = True, new: bool = True) -> Optional[str]:
    if new and len({k: v for (k, v) in c['legalities'].items() if 'Penny Dreadful' in k}) == (0 if speculation else 1):
        return 'new'
    p = playability.get(c.name, 0)
    if p > 0.1:
        return 'heavily-played'
    if p > 0.01:
        return 'moderately-played'
    return None

def text() -> str:
    full = next_rotation()
    supplemental = next_supplemental()
    now = dtutil.now()
    sdiff = supplemental - now
    diff = full - now
    if sdiff < diff:
        return 'The supplemental rotation is in {sdiff} (The next full rotation is in {diff})'.format(diff=dtutil.display_time(diff.total_seconds()), sdiff=dtutil.display_time(sdiff.total_seconds()))
    return 'The next rotation is in {diff}'.format(diff=dtutil.display_time(diff.total_seconds()))

__SETS: List[SetInfoType] = []
def sets() -> List[SetInfoType]:
    if not __SETS:
        __SETS.extend(init())
    return __SETS

def season_id(v: Union[int, str]) -> Union[int, str]:
    """From any value return the season id which is the integer representing the season, or 'all' for all time."""
    if v is None:
        return current_season_num()
    try:
        n = int(v)
        if SEASONS[n - 1]:
            return n
    except (ValueError, IndexError):
        pass
    try:
        if isinstance(v, str):
            if v.lower() == 'all':
                return 'all'
            return SEASONS.index(v.upper()) + 1
    except (ValueError, AttributeError):
        pass
    raise DoesNotExistException("I don't know a season called {v}".format(v=v))

def season_code(v: Union[int, str]) -> str:
    """From any value return the season code which is a three letter string representing the season, or 'ALL' for all time."""
    sid = season_id(v)
    if sid == 'all':
        return 'ALL'
    return SEASONS[int(sid) - 1]

def season_name(v: Union[int, str]) -> str:
    """From any value return the person-friendly name of the season, or 'All Time' for all time."""
    sid = season_id(v)
    if sid == 'all':
        return 'All Time'
    return 'Season {num}'.format(num=sid)

def files() -> List[str]:
    return sorted(glob.glob(os.path.join(configuration.get_str('legality_dir'), 'Run_*.txt')))

def get_set_info(code: str) -> SetInfoType:
    for setinfo in sets():
        if setinfo['code'] == code:
            return setinfo
    raise DoesNotExistException('Could not find Set Info about {code}'.format(code=code))
