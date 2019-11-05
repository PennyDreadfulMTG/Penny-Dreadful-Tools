import datetime
import glob
import os
from collections import Counter
from typing import Dict, List, Optional, Tuple, Union, cast

from mypy_extensions import TypedDict

from magic import fetcher, multiverse, oracle
from magic.models import Card
from shared import configuration, dtutil, redis, text
from shared.pd_exception import DoesNotExistException, InvalidDataException

TOTAL_RUNS = 168
WIS_DATE_FORMAT = '%Y-%m-%dT%H:%M:%S.%f'

DateType = TypedDict('DateType', {
    'exact': str,
    'rough': str,
})

SetInfoType = TypedDict('SetInfoType', {
    'name': str,
    'code': str,
    'codename': str,
    'mtgo_code': str,
    'enterDate': DateType,
    'exitDate': DateType,
    'enter_date_dt': datetime.datetime,
    })

SEASONS = [
    'EMN', 'KLD', # 2016
    'AER', 'AKH', 'HOU', 'XLN', # 2017
    'RIX', 'DOM', 'M19', 'GRN', # 2018
    'RNA', 'WAR', 'M20', 'ELD', # 2019
    ]

def init() -> List[SetInfoType]:
    info = fetcher.whatsinstandard()
    if info['deprecated']:
        print('Current whatsinstandard API version is DEPRECATED.')
    set_info = cast(List[SetInfoType], info['sets'])
    return [postprocess(release) for release in set_info if release['enterDate']['exact'] is not None]

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
    raise InvalidDataException('I did not find the season code (`{code}`) in the list of seasons ({seasons}) and I am confused.'.format(code=code_to_look_for, seasons=','.join(SEASONS)))

def last_rotation() -> datetime.datetime:
    return last_rotation_ex()['enter_date_dt']

def next_rotation() -> datetime.datetime:
    return next_rotation_ex()['enter_date_dt']

def next_rotation_any_kind() -> datetime.datetime:
    return min(next_rotation(), next_supplemental())

def last_rotation_ex() -> SetInfoType:
    return max([s for s in sets() if s['enter_date_dt'] < dtutil.now()], key=lambda s: s['enter_date_dt'])

def next_rotation_ex() -> SetInfoType:
    try:
        return min([s for s in sets() if s['enter_date_dt'] > dtutil.now()], key=lambda s: s['enter_date_dt'])
    except ValueError:
        fake_enter_date_dt = last_rotation() + datetime.timedelta(days=90)
        fake_exit_date_dt = last_rotation() + datetime.timedelta(days=90+365+365)
        fake_exit_year = fake_exit_date_dt.year
        fake_enter_date: DateType = {
            'exact': fake_enter_date_dt.strftime(WIS_DATE_FORMAT),
            'rough': 'Unknown'
        }
        fake_exit_date: DateType = {
            'exact': fake_exit_date_dt.strftime(WIS_DATE_FORMAT),
            'rough': f'Q4 {fake_exit_year}'
        }
        fake: SetInfoType = {
            'name': 'Unannounced Set',
            'code': '???',
            'mtgo_code': '???',
            'enterDate': fake_enter_date,
            'enter_date_dt': fake_enter_date_dt,
            'exitDate': fake_exit_date,
            'codename': 'Unannounced'
        }
        return fake

def next_supplemental() -> datetime.datetime:
    last = last_rotation() + datetime.timedelta(weeks=3)
    if last > dtutil.now():
        return last
    return next_rotation() + datetime.timedelta(weeks=3)

def this_supplemental() -> datetime.datetime:
    return last_rotation() + datetime.timedelta(weeks=3)

def postprocess(setinfo: SetInfoType) -> SetInfoType:
    setinfo['enter_date_dt'] = dtutil.parse(setinfo['enterDate']['exact'], WIS_DATE_FORMAT, dtutil.WOTC_TZ)
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

def message() -> str:
    full = next_rotation()
    supplemental = next_supplemental()
    now = dtutil.now()
    sdiff = supplemental - now
    diff = full - now
    if sdiff < diff:
        return 'The supplemental rotation is in {sdiff} (The next full rotation is in {diff})'.format(diff=dtutil.display_time(diff.total_seconds()), sdiff=dtutil.display_time(sdiff.total_seconds()))
    return 'The next rotation is in {diff}'.format(diff=dtutil.display_time(diff.total_seconds()))

def in_rotation() -> Tuple[bool, str]:
    if configuration.get_bool('always_show_rotation'):
        return True
    until_full_rotation = next_rotation() - dtutil.now()
    until_supplemental_rotation = next_supplemental() - dtutil.now()
    return until_full_rotation < datetime.timedelta(7) or until_supplemental_rotation < datetime.timedelta(7)

def next_rotation_is_supplemental() -> bool:
    full = next_rotation()
    supplemental = next_supplemental()
    now = dtutil.now()
    sdiff = supplemental - now
    diff = full - now
    return sdiff < diff


__SETS: List[SetInfoType] = []
def sets() -> List[SetInfoType]:
    if not __SETS:
        __SETS.extend(init())
    return __SETS

def season_id(v: Union[int, str], all_return_value: Optional[Union[int, str]] = 'all') -> Optional[Union[int, str]]:
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
                return all_return_value
            return SEASONS.index(v.upper()) + 1
    except (ValueError, AttributeError):
        pass
    raise DoesNotExistException("I don't know a season called {v}".format(v=v))

def season_code(v: Union[int, str]) -> str:
    """From any value return the season code which is a three letter string representing the season, or 'ALL' for all time."""
    sid = season_id(v)
    if sid == 'all' or sid is None:
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

def last_run_time() -> Optional[datetime.datetime]:
    try:
        return dtutil.ts2dt(int(os.path.getmtime(files()[-1])))
    except (IndexError, OSError):
        return None

def read_rotation_files() -> Tuple[int, int, List[Card]]:
    runs_str = redis.get_str('decksite:rotation:summary:runs')
    runs_percent_str = redis.get_str('decksite:rotation:summary:runs_percent')
    cards = redis.get_list('decksite:rotation:summary:cards')
    if runs_str is not None and runs_percent_str is not None and cards is not None:
        return int(runs_str), int(runs_percent_str), [Card(c, predetermined_values=True) for c in cards]
    lines = []
    fs = files()
    if len(fs) == 0:
        if not os.path.isdir(configuration.get_str('legality_dir')):
            raise DoesNotExistException('Invalid configuration.  Could not find legality_dir.')
        return (0, 0, [])
    latest_list = open(fs[-1], 'r').read().splitlines()
    for filename in fs:
        for line in get_file_contents(filename):
            line = text.sanitize(line)
            lines.append(line.strip())
    scores = Counter(lines).most_common()
    runs = scores[0][1]
    runs_percent = round(round(runs / TOTAL_RUNS, 2) * 100)
    cs = oracle.cards_by_name()
    cards = []
    for name, hits in scores:
        c = process_score(name, hits, cs, runs, latest_list)
        if c is not None:
            cards.append(c)
    redis.store('decksite:rotation:summary:runs', runs, ex=604800)
    redis.store('decksite:rotation:summary:runs_percent', runs_percent, ex=604800)
    redis.store('decksite:rotation:summary:cards', cards, ex=604800)
    return (runs, runs_percent, cards)

def get_file_contents(file: str) -> List[str]:
    key = f'decksite:rotation:file:{file}'
    contents = redis.get_list(key)
    if contents is not None:
        return contents
    with open(file) as f:
        contents = f.readlines()
    redis.store(key, contents, ex=604800)
    return contents

def clear_redis(clear_files: bool = False) -> None:
    redis.clear(*redis.keys('decksite:rotation:summary:*'))
    if clear_files:
        redis.clear(*redis.keys('decksite:rotation:file:*'))

def process_score(name: str, hits: int, cs: Dict[str, Card], runs: int, latest_list: List[str]) -> Optional[Card]:
    remaining_runs = TOTAL_RUNS - runs
    hits_needed = max(round(TOTAL_RUNS / 2 - hits), 0)
    c = cs[name]
    if c.layout not in multiverse.playable_layouts():
        return None
    percent = round(round(hits / runs, 2) * 100)
    if remaining_runs == 0:
        percent_needed = '0'
    else:
        percent_needed = str(round(round(hits_needed / remaining_runs, 2) * 100))
    if c is None:
        raise DoesNotExistException("Legality list contains unknown card '{name}'".format(name=name))
    if remaining_runs + hits < TOTAL_RUNS / 2:
        status = 'Not Legal'
    elif hits >= TOTAL_RUNS / 2:
        status = 'Legal'
    else:
        status = 'Undecided'
    hit_in_last_run = name in latest_list
    c.update({
        'hits': hits,
        'hits_needed': hits_needed,
        'percent': percent,
        'percent_needed': percent_needed,
        'status': status,
        'hit_in_last_run': hit_in_last_run
    })
    return c
