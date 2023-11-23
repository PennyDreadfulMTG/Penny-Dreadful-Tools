import datetime
import functools
from typing import List, Optional, Union

import attr

from magic import fetcher
from shared import dtutil, recursive_update
from shared.pd_exception import DoesNotExistException, InvalidDataException

WIS_DATE_FORMAT = '%Y-%m-%dT%H:%M:%S.%f'

SEASONS = [
    'EMN', 'KLD',                       # 2016
    'AER', 'AKH', 'HOU', 'XLN',         # 2017
    'RIX', 'DOM', 'M19', 'GRN',         # 2018
    'RNA', 'WAR', 'M20', 'ELD',         # 2019
    'THB', 'IKO', 'M21', 'ZNR',         # 2020
    'KHM', 'STX', 'AFR', 'MID', 'VOW',  # 2121
    'NEO', 'SNC', 'DMU', 'BRO',         # 2022
    'ONE', 'MOM', 'WOE', 'LCI',         # 2023
    'MKM',
]

NOT_SEASONS = [
    'March of the Machine: The Aftermath',  # Epilogue set, not rotation worthy
]

OVERRIDES = {
    'Dominaria': {  # Dominaria had a weird setcode in MTGO/Arena
        'mtgoCode': 'DAR',
    },
    'Ikoria: Lair of Behemoths': {  # Ikoria was delayed in NA because of Covid-19
        'enterDate': {
            'exact': '2020-04-17T00:00:00.000',
        },
    },
}

def rotation_offset(code: str) -> datetime.timedelta:
    if code in ['ONE', 'MOM']:
        return datetime.timedelta(days=14)
    return datetime.timedelta(days=7)


@attr.s(auto_attribs=True, slots=True)
class DateType():
    exact: str
    rough: str

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
        recursive_update.rupdate(json, OVERRIDES.get(json['name'], {}))  # type: ignore

        return cls(name=json['name'],
                   code=json['code'],
                   codename=json['codename'],
                   mtgo_code=json['mtgoCode'],
                   enter_date=DateType(**json['enterDate']),
                   exit_date=DateType(**json['exitDate']),
                   enter_date_dt=dtutil.parse(json['enterDate']['exact'], WIS_DATE_FORMAT, dtutil.WOTC_TZ) if json['enterDate']['exact'] else dtutil.ts2dt(0),
                   )

@attr.define()
class RotationInfo():
    next: SetInfo
    previous: SetInfo
    calculating: bool = False

    def validate(self) -> None:
        if (self.next.enter_date_dt + rotation_offset(self.next.code)) > dtutil.now():
            return
        if not self.calculating:
            self.recalculate()

    def recalculate(self) -> None:
        self.calculating = True
        self.previous = calc_prev()
        self.next = calc_next()
        self.calculating = False

def calc_next() -> SetInfo:
    try:
        return min([s for s in sets() if (s.enter_date_dt + rotation_offset(s.code)) > dtutil.now()], key=lambda s: s.enter_date_dt + rotation_offset(s.code))
    except ValueError:
        fake_enter_date_dt = calc_prev().enter_date_dt + datetime.timedelta(days=90)
        fake_exit_date_dt = calc_prev().enter_date_dt + datetime.timedelta(days=90 + 365 + 365)
        fake_exit_year = fake_exit_date_dt.year
        fake_enter_date = DateType(fake_enter_date_dt.strftime(WIS_DATE_FORMAT), 'Unknown')
        fake_exit_date = DateType(fake_exit_date_dt.strftime(WIS_DATE_FORMAT), f'Q4 {fake_exit_year}')

        return SetInfo('Unannounced Set', '???', '???', 'Unannounced', fake_enter_date, fake_exit_date, fake_enter_date_dt)

def calc_prev() -> SetInfo:
    return max([s for s in sets() if (s.enter_date_dt + rotation_offset(s.code)) < dtutil.now()], key=lambda s: s.enter_date_dt + rotation_offset(s.code))


@functools.lru_cache
def sets() -> List[SetInfo]:
    info = fetcher.whatsinstandard()
    if info['deprecated']:
        print('Current whatsinstandard API version is DEPRECATED.')
    set_info = [SetInfo.parse(s) for s in info['sets']]
    releases = []

    last = set_info[0]
    for s in set_info:
        if s.name in NOT_SEASONS:
            continue
        if s.enter_date_dt.timestamp() == 0:
            s.enter_date_dt = last.enter_date_dt + datetime.timedelta(days=90)
            print(f'guessing {s.name} enter date: {s.enter_date_dt}')
        releases.append(s)
        last = s
    return releases


@functools.lru_cache
def rotation_info() -> RotationInfo:
    return RotationInfo(calc_next(), calc_prev())

def current_season_code() -> str:
    return last_rotation_ex().code

def current_season_num() -> int:
    return season_num(current_season_code())

def current_season_name() -> str:
    return f'Penny Dreadful {current_season_code()}'

def season_num(code_to_look_for: str) -> int:
    try:
        return SEASONS.index(code_to_look_for) + 1
    except KeyError as c:
        raise InvalidDataException('I did not find the season code (`{code}`) in the list of seasons ({seasons}) and I am confused.'.format(code=code_to_look_for, seasons=','.join(SEASONS))) from c

def last_rotation() -> datetime.datetime:
    s = last_rotation_ex()
    return s.enter_date_dt + rotation_offset(s.code)

def next_rotation() -> datetime.datetime:
    s = next_rotation_ex()
    return s.enter_date_dt + rotation_offset(s.code)

def last_rotation_ex() -> SetInfo:
    rotation_info().validate()
    return rotation_info().previous

def next_rotation_ex() -> SetInfo:
    rotation_info().validate()
    return rotation_info().next

def message() -> str:
    upcoming = next_rotation_ex()
    diff = next_rotation() - dtutil.now()
    s = dtutil.display_time(int(diff.total_seconds()))
    if upcoming.code == '???':
        s = dtutil.display_time(int(diff.total_seconds()), 1)
        return f'The next rotation is roughly {s} away'
    return f'The next rotation is in {s}'

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
    assert sid is not None  # For typechecking which can't understand the above if statement.
    return SEASONS[int(sid) - 1]

def season_name(v: Union[int, str]) -> str:
    """From any value return the person-friendly name of the season, or 'All Time' for all time."""
    sid = season_id(v)
    if sid in ('all', 0):
        return 'All Time'
    return 'Season {num}'.format(num=sid)

def get_set_info(code: str) -> SetInfo:
    for setinfo in sets():
        if setinfo.code == code:
            return setinfo
    raise DoesNotExistException('Could not find Set Info about {code}'.format(code=code))
