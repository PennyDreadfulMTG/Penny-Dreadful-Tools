import datetime
import glob
import os
from collections import Counter
from typing import Dict, List, Optional, Tuple, Union

import attr

from magic import fetcher, multiverse, oracle
from magic.models import Card
from shared import configuration, dtutil
from shared import redis_wrapper as redis
from shared import text
from shared.pd_exception import DoesNotExistException, InvalidDataException

TOTAL_RUNS = 168
WIS_DATE_FORMAT = '%Y-%m-%dT%H:%M:%S.%f'
ROTATION_OFFSET = datetime.timedelta(days=7) # We rotate seven days after a set is released.

SEASONS = [
    'EMN', 'KLD', # 2016
    'AER', 'AKH', 'HOU', 'XLN', # 2017
    'RIX', 'DOM', 'M19', 'GRN', # 2018
    'RNA', 'WAR', 'M20', 'ELD', # 2019
    'THB', 'IKO', 'M21', 'ZNR', # 2020
    ]

@attr.s(auto_attribs=True, slots=True)
class DateType():
    exact: str
    rough: str

OVERRIDES = {
    'Dominaria': { # Dominaria had a weird setcode in MTGO/Arena
        'mtgoCode': 'DAR'
    },
    'Ikoria: Lair of Behemoths': {  # Ikoria was delayed in NA because of Covid-19
        'enterDate': {
            'exact': '2020-04-17T00:00:00.000',
            'rough': 'April 2020'
        }
    },
}

@attr.s(auto_attribs=True, slots=True)
class SetInfo():
    name: str
    code: str
    codename: str
    mtgo_code: str
    enter_date: DateType
    exit_date: DateType
    enter_date_dt: datetime.datetime

    @classmethod
    def parse(cls, json: 'fetcher.WISSetInfoType') -> 'SetInfo':
        json['mtgoCode'] = json['code']
        json.update(OVERRIDES.get(json['name'], {})) # type: ignore

        return cls(name=json['name'],
                   code=json['code'],
                   codename=json['codename'],
                   mtgo_code=json['mtgoCode'],
                   enter_date=DateType(**json['enterDate']),
                   exit_date=DateType(**json['exitDate']),
                   enter_date_dt=dtutil.parse(json['enterDate']['exact'], WIS_DATE_FORMAT, dtutil.WOTC_TZ) if json['enterDate']['exact'] else dtutil.ts2dt(0)
                   )

def init() -> List[SetInfo]:
    info = fetcher.whatsinstandard()
    if info['deprecated']:
        print('Current whatsinstandard API version is DEPRECATED.')
    set_info = [SetInfo.parse(s) for s in info['sets']]
    return [release for release in set_info if release.enter_date.exact is not None]

def current_season_code() -> str:
    return last_rotation_ex().code

def current_season_num() -> int:
    return season_num(current_season_code())

def season_num(code_to_look_for: str) -> int:
    try:
        return SEASONS.index(code_to_look_for) + 1
    except KeyError as c:
        raise InvalidDataException('I did not find the season code (`{code}`) in the list of seasons ({seasons}) and I am confused.'.format(code=code_to_look_for, seasons=','.join(SEASONS))) from c

def last_rotation() -> datetime.datetime:
    return last_rotation_ex().enter_date_dt + ROTATION_OFFSET

def next_rotation() -> datetime.datetime:
    return next_rotation_ex().enter_date_dt + ROTATION_OFFSET

def last_rotation_ex() -> SetInfo:
    return max([s for s in sets() if (s.enter_date_dt + ROTATION_OFFSET) < dtutil.now()], key=lambda s: s.enter_date_dt + ROTATION_OFFSET)

def next_rotation_ex() -> SetInfo:
    try:
        return min([s for s in sets() if (s.enter_date_dt + ROTATION_OFFSET) > dtutil.now()], key=lambda s: s.enter_date_dt + ROTATION_OFFSET)
    except ValueError:
        fake_enter_date_dt = last_rotation() + datetime.timedelta(days=90)
        fake_exit_date_dt = last_rotation() + datetime.timedelta(days=90+365+365)
        fake_exit_year = fake_exit_date_dt.year
        fake_enter_date = DateType(fake_enter_date_dt.strftime(WIS_DATE_FORMAT), 'Unknown')
        fake_exit_date = DateType(fake_exit_date_dt.strftime(WIS_DATE_FORMAT), f'Q4 {fake_exit_year}')

        fake = SetInfo('Unannounced Set', '???', '???', 'Unannounced', fake_enter_date, fake_exit_date, fake_enter_date_dt)
        return fake

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
    diff = next_rotation() - dtutil.now()
    s = dtutil.display_time(int(diff.total_seconds()))
    return f'The next rotation is in {s}'

def in_rotation() -> bool:
    if configuration.get_bool('always_show_rotation'):
        return True
    until_rotation = next_rotation() - dtutil.now()
    return until_rotation < datetime.timedelta(7)


__SETS: List[SetInfo] = []
def sets() -> List[SetInfo]:
    if not __SETS:
        __SETS.extend(init())
    return __SETS

def season_id(v: Union[int, str], all_return_value: Optional[Union[int, str]] = 'all') -> Optional[Union[int, str]]:
    """From any value return the season id which is the integer representing the season, or all_return_value (default 'all') for all time."""
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
    if sid in ('all', 0, None):
        return 'ALL'
    assert sid is not None # For typechecking which can't understand the above if statement.
    return SEASONS[int(sid) - 1]

def season_name(v: Union[int, str]) -> str:
    """From any value return the person-friendly name of the season, or 'All Time' for all time."""
    sid = season_id(v)
    if sid in ('all', 0):
        return 'All Time'
    return 'Season {num}'.format(num=sid)

def files() -> List[str]:
    return sorted(glob.glob(os.path.expanduser(os.path.join(configuration.get_str('legality_dir'), 'Run_*.txt'))))

def get_set_info(code: str) -> SetInfo:
    for setinfo in sets():
        if setinfo.code == code:
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
    return rotation_redis_store()

def rotation_redis_store() -> Tuple[int, int, List[Card]]:
    lines = []
    fs = files()
    if len(fs) == 0:
        if not os.path.isdir(os.path.expanduser(configuration.get_str('legality_dir'))):
            print('WARNING: Could not find legality_dir.')
        return (0, 0, [])
    with open(fs[-1], 'r') as f:
        latest_list = f.read().splitlines()
    for filename in fs:
        for line in get_file_contents(filename):
            line = text.sanitize(line)
            lines.append(line.strip())
    scores = Counter(lines).most_common()
    runs = scores[0][1]
    runs_percent = round(round(runs / TOTAL_RUNS, 2) * 100)
    cs = oracle.cards_by_name()
    cards = []
    card_names_by_status: Dict[str, List[str]] = {}
    for name, hits in scores:
        c = process_score(name, hits, cs, runs, latest_list)
        if c is not None:
            cards.append(c)
            classify_by_status(c, card_names_by_status)
    redis.store('decksite:rotation:summary:runs', runs, ex=300)
    redis.store('decksite:rotation:summary:runs_percent', runs_percent, ex=604800)
    redis.store('decksite:rotation:summary:cards', cards, ex=604800)
    if 'Undecided' in card_names_by_status:
        redis.sadd('decksite:rotation:summary:undecided', *card_names_by_status['Undecided'], ex=604800)
    if 'Legal' in card_names_by_status:
        redis.sadd('decksite:rotation:summary:legal', *card_names_by_status['Legal'], ex=604800)
    if 'Not Legal' in card_names_by_status:
        redis.sadd('decksite:rotation:summary:notlegal', *card_names_by_status['Not Legal'], ex=604800)
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
    if not multiverse.is_playable_layout(c.layout):
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

def classify_by_status(c: Card, card_names_by_status: Dict[str, List[str]]) -> None:
    if not c.status in card_names_by_status:
        card_names_by_status[c.status] = []
    card_names_by_status[c.status].append(c.name)
