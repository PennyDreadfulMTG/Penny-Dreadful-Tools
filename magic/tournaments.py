import datetime
import sys
from enum import Enum
from typing import Any, Dict, List, Tuple

import inflect
from dateutil import rrule  # type: ignore # dateutil stubs are incomplete

from magic.models import Deck
from shared import dtutil, guarantee
from shared.container import Container

TournamentDateType = Tuple[str, datetime.datetime]

class TimeDirection(Enum):
    BEFORE = 1
    AFTER = 2

def next_tournament_info() -> Dict[str, Any]:
    return tournament_info(TimeDirection.AFTER)

def previous_tournament_info() -> Dict[str, Any]:
    return tournament_info(TimeDirection.BEFORE, units=1)

def tournament_info(time_direction: TimeDirection, units: int = 2) -> Dict[str, Any]:
    name, time = get_nearest_tournament(time_direction)
    next_tournament_time_precise = abs(dtutil.dt2ts(time) - dtutil.dt2ts(dtutil.now()))
    near = next_tournament_time_precise < 18000 # Threshold for near: 5 hours in seconds
    next_tournament_time = dtutil.display_time(next_tournament_time_precise, units)
    info = {
        'next_tournament_name': name,
        'next_tournament_time': next_tournament_time,
        'next_tournament_time_precise': next_tournament_time_precise,
        'near': near
    }
    info.update(series_info(name))
    return info

def get_nearest_tournament(time_direction: TimeDirection = TimeDirection.AFTER) -> TournamentDateType:
    start = dtutil.now(dtutil.GATHERLING_TZ)
    if time_direction == TimeDirection.AFTER:
        index = 0
    else:
        index = -1
        start = start - datetime.timedelta(days=7)

    dates = get_all_next_tournament_dates(start, index=index)
    return sorted(dates, key=lambda t: t[1])[index]

def get_all_next_tournament_dates(start: datetime.datetime, index: int = 0) -> List[TournamentDateType]:
    apac_start = start.astimezone(tz=dtutil.APAC_SERIES_TZ)
    until = start + datetime.timedelta(days=7)
    pdsat_time = ('Penny Dreadful Saturdays', rrule.rrule(rrule.WEEKLY, byhour=13, byminute=30, bysecond=0, dtstart=start, until=until, byweekday=rrule.SA)[index])
    apds_time = ('APAC Penny Dreadful Sundays', rrule.rrule(rrule.WEEKLY, byhour=16, byminute=0, bysecond=0, dtstart=apac_start, until=until, byweekday=rrule.SU)[index])
    pds_time = ('Penny Dreadful Sundays', rrule.rrule(rrule.WEEKLY, byhour=13, byminute=30, bysecond=0, dtstart=start, until=until, byweekday=rrule.SU)[index])
    pdm_time = ('Penny Dreadful Mondays', rrule.rrule(rrule.WEEKLY, byhour=19, byminute=0, bysecond=0, dtstart=start, until=until, byweekday=rrule.MO)[index])
    pdt_time = ('Penny Dreadful Thursdays', rrule.rrule(rrule.WEEKLY, byhour=19, byminute=0, bysecond=0, dtstart=start, until=until, byweekday=rrule.TH)[index])
    return [pdsat_time, apds_time, pds_time, pdm_time, pdt_time]

def prize(d: Deck) -> int:
    return prize_by_finish(d.get('finish') or sys.maxsize)

def prize_by_finish(f: int) -> int:
    if f == 1:
        return 4
    if f == 2:
        return 3
    if f <= 4:
        return 2
    if f <= 8:
        return 1
    return 0

def prizes_by_finish(multiplier: int = 1) -> List[Dict[str, Any]]:
    prizes, finish, p = [], 1, inflect.engine()
    while True:
        pz = prize_by_finish(finish)
        if not pz:
            break
        prizes.append({'finish': p.ordinal(finish), 'prize': pz * multiplier})
        finish += 1
    return prizes

def series_info(name: str) -> Container:
    return guarantee.exactly_one([s for s in all_series_info() if s.name == name])

def all_series_info() -> List[Container]:
    info = get_all_next_tournament_dates(dtutil.now(dtutil.GATHERLING_TZ))
    return [
        Container({
            'name': 'Penny Dreadful Saturdays',
            'hosts': ['pseudodude', 'j_meka'],
            'display_time': '1:30pm Eastern',
            'time': info[0][1],
            'sponsor_name': 'Cardhoarder'
        }),
        Container({
            'name': 'APAC Penny Dreadful Sundays',
            'hosts': ['silasary', 'jgabrielygalan'],
            'display_time': '4pm Japan Standard Time',
            'time': info[1][1],
            'sponsor_name': 'Cardhoarder'
        }),
        Container({
            'name': 'Penny Dreadful Sundays',
            'hosts': ['mrsad', 'bakert99'],
            'display_time': '1:30pm Eastern',
            'time': info[2][1],
            'sponsor_name': 'Cardhoarder'
        }),
        Container({
            'name': 'Penny Dreadful Mondays',
            'hosts': ['briar_moss', 'j_meka'],
            'display_time': '7pm Eastern',
            'time': info[3][1],
            'sponsor_name': 'Cardhoarder'
        }),
        Container({
            'name': 'Penny Dreadful Thursdays',
            'hosts': ['silasary', 'j_meka'],
            'display_time': '7pm Eastern',
            'time': info[4][1],
            'sponsor_name': 'Cardhoarder'
        })
    ]
