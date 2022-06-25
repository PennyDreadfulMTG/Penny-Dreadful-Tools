import datetime
import sys
from enum import Enum
from itertools import groupby
from typing import Any, Dict, List, Tuple, Union

import inflect
from dateutil import rrule

from magic import seasons
from magic.models import Competition, Deck
from shared import dtutil, guarantee
from shared.container import Container

TournamentDateType = Tuple[int, str, datetime.datetime]
Prizes = List[Dict[str, Union[str, object]]]

FNM = 1
SAT = 2
APAC = 3
SUN = 4
MON = 5
TUE = 6
THU = 7

class TimeDirection(Enum):
    BEFORE = 1
    AFTER = 2

class StageType(Enum):
    SWISS_ROUNDS = 'swiss_rounds'
    ELIMINATION_ROUNDS = 'elimination_rounds'


def next_tournament_info() -> Dict[str, Any]:
    return tournament_info(TimeDirection.AFTER)

def previous_tournament_info() -> Dict[str, Any]:
    return tournament_info(TimeDirection.BEFORE, units=1)

def tournament_info(time_direction: TimeDirection, units: int = 2) -> Dict[str, Any]:
    tournament_id, name, time = get_nearest_tournament(time_direction)
    next_tournament_time_precise = abs(dtutil.dt2ts(time) - dtutil.dt2ts(dtutil.now()))
    near = next_tournament_time_precise < 18000  # Threshold for near: 5 hours in seconds
    next_tournament_time = dtutil.display_time(next_tournament_time_precise, units)
    info = {
        'next_tournament_name': name,
        'next_tournament_time': next_tournament_time,
        'next_tournament_time_precise': next_tournament_time_precise,
        'near': near,
        'discord_relative': f'<t:{dtutil.dt2ts(time)}:R>',
        'discord_full': f'<t:{dtutil.dt2ts(time)}:F>',
    }
    info.update(series_info(tournament_id))
    return info

def get_nearest_tournament(time_direction: TimeDirection = TimeDirection.AFTER) -> TournamentDateType:
    start = dtutil.now(dtutil.GATHERLING_TZ)
    if time_direction == TimeDirection.AFTER:
        index = 0
    else:
        index = -1
        start = start - datetime.timedelta(days=7)

    dates = get_all_next_tournament_dates(start, index=index)
    return sorted(dates, key=lambda t: t[2])[index]

def get_all_next_tournament_dates(start: datetime.datetime, index: int = 0) -> List[TournamentDateType]:
    apac_start = start.astimezone(tz=dtutil.APAC_SERIES_TZ)
    until = start + datetime.timedelta(days=7)
    pdfnm_time = (FNM, 'Penny Dreadful FNM', rrule.rrule(rrule.WEEKLY, byhour=19, byminute=0, bysecond=0, dtstart=start, until=until, byweekday=rrule.FR)[index])
    if is_pd500_week(start):
        pdsat_name = 'The Penny Dreadful 500'
    elif is_kick_off_week(start):
        pdsat_name = 'Season Kick Off'
    else:
        pdsat_name = 'Penny Dreadful Saturdays'
    pdsat_time = (SAT, pdsat_name, rrule.rrule(rrule.WEEKLY, byhour=13, byminute=30, bysecond=0, dtstart=start, until=until, byweekday=rrule.SA)[index])
    apds_time = (APAC, 'APAC Penny Dreadful Sundays', rrule.rrule(rrule.WEEKLY, byhour=16, byminute=0, bysecond=0, dtstart=apac_start, until=until, byweekday=rrule.SU)[index])
    pds_time = (SUN, 'Penny Dreadful Sundays', rrule.rrule(rrule.WEEKLY, byhour=13, byminute=30, bysecond=0, dtstart=start, until=until, byweekday=rrule.SU)[index])
    pdm_time = (MON, 'Penny Dreadful Mondays', rrule.rrule(rrule.WEEKLY, byhour=19, byminute=0, bysecond=0, dtstart=start, until=until, byweekday=rrule.MO)[index])
    pdtue_time = (TUE, 'Penny Dreadful Tuesdays', rrule.rrule(rrule.WEEKLY, byhour=20, byminute=0, bysecond=0, dtstart=start, until=until, byweekday=rrule.TU)[index])
    pdthu_time = (THU, 'Penny Dreadful Thursdays', rrule.rrule(rrule.WEEKLY, byhour=19, byminute=0, bysecond=0, dtstart=start, until=until, byweekday=rrule.TH)[index])
    return [pdfnm_time, pdsat_time, apds_time, pds_time, pdm_time, pdtue_time, pdthu_time]

# Note: this may be in the past. It always gives the date for the current season.
# Note: if the start date of next season is not known then the date of the PD 500 cannot be known and in such a case this return None.
def pd500_date() -> datetime.datetime:
    if seasons.next_rotation_ex().codename == '???':
        return datetime.datetime(1970, 1, 1, tzinfo=dtutil.GATHERLING_TZ)

    end_of_season = seasons.next_rotation()
    return end_of_season - datetime.timedelta(days=5, hours=13, minutes=30)  # This effectively hardcodes a 10:30 PD Sat start time AND a Thu/Fri midnight rotation time.

def is_pd500_week(start: datetime.datetime) -> bool:
    date_of_pd500 = pd500_date()
    return start <= date_of_pd500 <= start + datetime.timedelta(days=7)

# Note: this may be in the past. It always gives the date for the current season.
def kick_off_date() -> datetime.datetime:
    start_of_season = seasons.last_rotation()
    return start_of_season + datetime.timedelta(days=8, hours=10, minutes=30)  # This effectively hardcodes a 10:30 PD Sat start time AND a Thu/Fri midnight rotation time.

def is_kick_off_week(start: datetime.datetime) -> bool:
    date_of_kick_off = kick_off_date()
    return start <= date_of_kick_off <= start + datetime.timedelta(days=7)

def is_pd500(c: Competition) -> bool:
    return 'Penny Dreadful 500' in c.name

def is_kick_off(c: Competition) -> bool:
    return 'Kick Off' in c.name or 'Kickoff' in c.name

def pd500_prizes() -> Prizes:
    return display_prizes(prizes_by_finish(Competition({'name': 'Penny Dreadful 500'})))

def kick_off_prizes() -> Prizes:
    return display_prizes(prizes_by_finish(Competition({'name': 'Kick Off'})))

def normal_prizes() -> Prizes:
    return display_prizes(prizes_by_finish(Competition({'name': ''})))

def prizes_by_finish(c: Competition) -> Prizes:
    prizes, finish, p = [], 1, inflect.engine()
    while True:
        pz = prize_by_finish(c, finish)
        if not pz:
            break
        prizes.append({'finish': p.ordinal(finish), 'prize': pz})
        finish += 1
    return prizes

def display_prizes(prizes: Prizes) -> Prizes:
    r = []
    grouped = groupby(prizes, key=lambda x: x.get('prize', 0))
    for p, i in grouped:
        items = list(i)
        finish = str(items[0].get('finish', '')) if len(items) == 1 else str(items[0].get('finish', '')) + '–' + str(items[-1].get('finish', ''))
        r.append({'finish': finish, 'prize': p})
    return r

def prize(c: Competition, d: Deck) -> int:
    finish = d.get('finish') or sys.maxsize
    return prize_by_finish(c, finish)

def prize_by_finish(c: Competition, finish: int) -> int:
    if is_pd500(c):
        return pd500_prize(finish)
    if is_kick_off(c):
        return kick_off_prize(finish)
    return normal_prize(finish)

def pd500_prize(f: int) -> int:
    if f == 1:
        return 130
    if f == 2:
        return 90
    if f <= 4:
        return 60
    if f <= 8:
        return 30
    if f <= 16:
        return 10
    return 0

def kick_off_prize(f: int) -> int:
    if f == 1:
        return 25
    if f == 2:
        return 20
    if f <= 4:
        return 15
    if f <= 8:
        return 10
    if f <= 16:
        return 5
    if f <= 24:
        return 2
    if f <= 32:
        return 1
    return 0

def normal_prize(f: int) -> int:
    if f == 1:
        return 4
    if f == 2:
        return 3
    if f <= 4:
        return 2
    if f <= 8:
        return 1
    return 0

def series_info(tournament_id: int) -> Container:
    return guarantee.exactly_one([s for s in all_series_info() if s.tournament_id == tournament_id])

def all_series_info() -> List[Container]:
    info = get_all_next_tournament_dates(dtutil.now(dtutil.GATHERLING_TZ))
    return [
        Container({
            'tournament_id': info[0][0],
            'name': info[0][1],
            'hosts': ['flac0', 'j_meka'],
            'display_time': '7pm Eastern',
            'time': info[0][2],
            'sponsor_name': 'Cardhoarder',

        }),
        Container({
            'tournament_id': info[1][0],
            'name': info[1][1],
            'hosts': ['j_meka', 'crazybaloth'],
            'display_time': '1:30pm Eastern',
            'time': info[1][2],
            'sponsor_name': 'Cardhoarder',
        }),
        Container({
            'tournament_id': info[2][0],
            'name': info[2][1],
            'hosts': ['jgabrielygalan', 'silasary'],
            'display_time': '4pm Japan Standard Time',
            'time': info[2][2],
            'sponsor_name': 'Cardhoarder',
        }),
        Container({
            'tournament_id': info[3][0],
            'name': info[3][1],
            'hosts': ['cody_', 'bakert99'],
            'display_time': '1:30pm Eastern',
            'time': info[3][2],
            'sponsor_name': 'Cardhoarder',
        }),
        Container({
            'tournament_id': info[4][0],
            'name': info[4][1],
            'hosts': ['briar_moss', 'j_meka'],
            'display_time': '7pm Eastern',
            'time': info[4][2],
            'sponsor_name': 'Cardhoarder',
        }),
        Container({
            'tournament_id': info[5][0],
            'name': info[5][1],
            'hosts': ['tiggu', 'bakert99'],
            'display_time': '7pm Eastern',
            'time': info[5][2],
            'sponsor_name': None,
        }),
        Container({
            'tournament_id': info[6][0],
            'name': info[6][1],
            'hosts': ['flac0', 'j_meka'],
            'display_time': '7pm Eastern',
            'time': info[6][2],
            'sponsor_name': 'Cardhoarder',
        }),
    ]

def rounds_info() -> List[Dict[Union[str, StageType], int]]:
    return [
        {
            'min_players': 2,
            'max_players': 2,
            StageType.SWISS_ROUNDS: 0,
            StageType.ELIMINATION_ROUNDS: 1,
        },
        {
            'min_players': 3,
            'max_players': 7,
            StageType.SWISS_ROUNDS: 3,
            StageType.ELIMINATION_ROUNDS: 0,
        },
        {
            'min_players': 8,
            'max_players': 8,
            StageType.SWISS_ROUNDS: 3,
            StageType.ELIMINATION_ROUNDS: 2,
        },
        {
            'min_players': 9,
            'max_players': 15,
            StageType.SWISS_ROUNDS: 4,
            StageType.ELIMINATION_ROUNDS: 2,
        },
        {
            'min_players': 16,
            'max_players': 31,
            StageType.SWISS_ROUNDS: 4,
            StageType.ELIMINATION_ROUNDS: 3,
        },
        {
            'min_players': 32,
            'max_players': sys.maxsize,
            StageType.SWISS_ROUNDS: 5,
            StageType.ELIMINATION_ROUNDS: 3,
        },
    ]

def num_rounds_info(num_players: int, k: StageType) -> int:
    for entry in rounds_info():
        if (entry['min_players'] is not None and num_players >= entry['min_players']) and (entry['max_players'] is None or num_players <= entry['max_players']):
            return entry[k]
    return 0
