import datetime
import functools
import sys

import attr

from magic import fetcher
from shared import dtutil, recursive_update
from shared.pd_exception import DoesNotExistException, InvalidDataException

ALL = 'ALL'

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
    'MKM', 'OTJ', 'BLB', 'DSK', 'FDN',  # 2024
    'DFT', 'FIN', 'SPM', 'TLA',         # 2025
    'Wrestling', 'Yachting',            # 2026
]

SUPPLEMENTAL_SETS = [
    'MAT',  # March of the Machines Aftermath, mini-set
    'TDM', 'EOE',  # 2025
    'TMT', 'Ziplining' # 2026
]

IGNORED_SETS = [
    'OM1',  # Through the Omenpaths, equivalent to SPM
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
    elif code in SEASONS and SEASONS.index(code) >= SEASONS.index('SPM'):
        return datetime.timedelta(days=14)
    elif code in SUPPLEMENTAL_SETS and SUPPLEMENTAL_SETS.index(code) >= SUPPLEMENTAL_SETS.index('EOE'):
        return datetime.timedelta(days=14)
    return datetime.timedelta(days=7)


@attr.s(auto_attribs=True, slots=True)
class DateType:
    exact: str
    rough: str

@attr.s(auto_attribs=True, slots=True)
class SetInfo:
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
        if json['name'] is None:
            json['name'] = json['codename']

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
class RotationInfo:
    next: SetInfo
    previous: SetInfo
    next_supplemental: SetInfo | None
    previous_supplemental: SetInfo
    calculating: bool = False

    def validate(self) -> None:
        if (self.next.enter_date_dt + rotation_offset(self.next.code)) > dtutil.now():
            return
        if not self.calculating:
            self.recalculate()

    def recalculate(self) -> None:
        self.calculating = True
        self.previous = calc_prev(False)
        self.next = calc_next(False)
        self.previous_supplemental = calc_prev(True)
        self.next_supplemental = calc_next(True)
        self.calculating = False

def calc_next(supplemental: bool) -> SetInfo:
    try:
        return min([s for s in sets(supplemental) if (s.enter_date_dt + rotation_offset(s.code)) > dtutil.now()], key=lambda s: s.enter_date_dt + rotation_offset(s.code))
    except ValueError:
        fake_enter_date_dt = calc_prev(None).enter_date_dt + datetime.timedelta(days=90)
        fake_exit_date_dt = calc_prev(None).enter_date_dt + datetime.timedelta(days=90 + 365 + 365)
        fake_exit_year = fake_exit_date_dt.year
        fake_enter_date = DateType(fake_enter_date_dt.strftime(WIS_DATE_FORMAT), 'Unknown')
        fake_exit_date = DateType(fake_exit_date_dt.strftime(WIS_DATE_FORMAT), f'Q4 {fake_exit_year}')

        return SetInfo('Unannounced Set', '???', '???', 'Unannounced', fake_enter_date, fake_exit_date, fake_enter_date_dt)

def calc_prev(supplemental: bool | None) -> SetInfo:
    return max([s for s in sets(supplemental) if (s.enter_date_dt + rotation_offset(s.code)) < dtutil.now()], key=lambda s: s.enter_date_dt + rotation_offset(s.code))


@functools.lru_cache
def sets(supplemental: bool | None) -> list[SetInfo]:
    info = fetcher.whatsinstandard()
    if info['deprecated']:
        print('Current whatsinstandard API version is DEPRECATED.')
    set_info = [SetInfo.parse(s) for s in info['sets'] if s['code'] not in IGNORED_SETS]
    releases = []

    last = set_info[0]
    for s in set_info:
        if s.codename in SEASONS and s.code is not None:
            SEASONS[SEASONS.index(s.codename)] = s.code
            print(f'Updating season code {s.codename} to {s.code}', file=sys.stderr)
        elif s.codename in SUPPLEMENTAL_SETS and s.code is not None:
            SUPPLEMENTAL_SETS[SUPPLEMENTAL_SETS.index(s.codename)] = s.code
            print(f'Updating supplemental set code {s.codename} to {s.code}', file=sys.stderr)
        if supplemental is None:
            pass
        elif supplemental and s.code not in SUPPLEMENTAL_SETS:
            continue
        elif not supplemental and s.code in SUPPLEMENTAL_SETS:
            continue
        if s.enter_date_dt.timestamp() == 0:
            s.enter_date_dt = last.enter_date_dt + datetime.timedelta(days=90)
            print(f'guessing {s.name} enter date: {s.enter_date_dt}', file=sys.stderr)
        releases.append(s)
        last = s
    return releases


@functools.lru_cache
def rotation_info() -> RotationInfo:
    return RotationInfo(calc_next(False), calc_prev(False), calc_next(True), calc_prev(True))

def current_season_code() -> str:
    return last_rotation_ex().code

def current_season_num() -> int:
    return season_num(current_season_code())

def current_season_name() -> str:
    return f'Penny Dreadful {current_season_code()}'

def next_season_num() -> int:
    return current_season_num() + 1

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

def next_supplemental_ex() -> SetInfo | None:
    rotation_info().validate()
    return rotation_info().next_supplemental

def next_supplemental() -> datetime.datetime:
    s = next_supplemental_ex()
    if s:
        return s.enter_date_dt + rotation_offset(s.code)
    return datetime.datetime.max

def last_supplemental_ex() -> SetInfo:
    rotation_info().validate()
    return rotation_info().previous_supplemental

def last_supplemental() -> datetime.datetime:
    s = last_supplemental_ex()
    return s.enter_date_dt + rotation_offset(s.code)

def last_rotation_ex() -> SetInfo:
    rotation_info().validate()
    return rotation_info().previous

def next_rotation_ex() -> SetInfo:
    rotation_info().validate()
    return rotation_info().next

def message() -> str:
    full = next_rotation()
    supplemental = next_supplemental()
    now = dtutil.now()
    sdiff = supplemental - now
    diff = full - now
    full_display = dtutil.display_time(diff.total_seconds())
    if sdiff < diff:
        sup_display = dtutil.display_time(sdiff.total_seconds())
        return f'The supplemental rotation is in {sup_display} (The next full rotation is in {full_display})'
    upcoming = next_rotation_ex()
    if upcoming.code == '???':
        full_display = dtutil.display_time(int(diff.total_seconds()), 1)
        return f'The next rotation is roughly {full_display} away'
    return f'The next rotation is in {full_display}'

def season_id(v: int | str, all_return_value: int | str | None = 'all') -> int | str | None:
    """From any value return the season id which is the integer representing the season, or all_return_value (default 'all') for all time."""
    if v is None:
        return current_season_num()
    try:
        n = int(v)
        if n < 0:
            raise DoesNotExistException(f'Invalid season id {n}')
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
    raise DoesNotExistException(f"I don't know a season called {v}")

def season_code(v: int | str) -> str:
    """From any value return the season code which is a three letter string representing the season, or 'ALL' for all time."""
    sid = season_id(v)
    if sid in ('all', 0, None):
        return 'ALL'
    assert sid is not None  # For typechecking which can't understand the above if statement.
    return SEASONS[int(sid) - 1]

def season_name(v: int | str) -> str:
    """From any value return the person-friendly name of the season, or 'All Time' for all time."""
    sid = season_id(v)
    if sid in ('all', 0):
        return 'All Time'
    return f'Season {sid}'

def get_set_info(code: str) -> SetInfo:
    for setinfo in sets(True):
        if setinfo.code == code:
            return setinfo
    for setinfo in sets(False):
        if setinfo.code == code:
            return setinfo
    raise DoesNotExistException(f'Could not find Set Info about {code}')
