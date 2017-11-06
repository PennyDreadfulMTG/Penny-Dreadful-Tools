import sys

from dateutil import rrule

from shared import dtutil

def next_tournament_info():
    now = dtutil.now(dtutil.GATHERLING_TZ)
    now_ts = dtutil.dt2ts(dtutil.now())
    pdsat_time = rrule.rrule(rrule.WEEKLY, byhour=13, byminute=30, bysecond=0, dtstart=now, byweekday=rrule.SA)[0]
    pds_time = rrule.rrule(rrule.WEEKLY, byhour=13, byminute=30, bysecond=0, dtstart=now, byweekday=rrule.SU)[0]
    pdm_time = rrule.rrule(rrule.WEEKLY, byhour=19, byminute=0, bysecond=0, dtstart=now, byweekday=rrule.MO)[0]
    pdt_time = rrule.rrule(rrule.WEEKLY, byhour=19, byminute=0, bysecond=0, dtstart=now, byweekday=rrule.TH)[0]
    next_time = min([pdsat_time, pds_time, pdm_time, pdt_time])
    if next_time == pdsat_time:
        day = 'Saturday'
    elif next_time == pds_time:
        day = 'Sunday'
    elif next_time == pdm_time:
        day = 'Monday'
    else:
        day = 'Thursday'
    next_tournament_name = 'Penny Dreadful {day}'.format(day=day)
    next_tournament_time_precise = dtutil.dt2ts(next_time) - now_ts
    next_tournament_time = dtutil.display_time(next_tournament_time_precise)
    return {
        'next_tournament_name': next_tournament_name,
        'next_tournament_time': next_tournament_time,
        'next_tournament_time_precise': next_tournament_time_precise,
        'pdsat_time': pdsat_time,
        'pds_time': pds_time,
        'pdm_time': pdm_time,
        'pdt_time': pdt_time
    }

def prize(d):
    f = d.get('finish') or sys.maxsize
    if f == 1:
        return 4
    elif f == 2:
        return 3
    elif f <= 4:
        return 2
    elif f <= 8:
        return 1
    return 0

def all_series_info():
    info = next_tournament_info()
    return [
        {
            'name': 'Penny Dreadful Saturdays',
            'hosts': ['back_alley_g', 'bigm'],
            'display_time': '1:30pm Eastern',
            'time': info['pdsat_time'],
            'chat_room': '#PDS'
        },
        {
            'name': 'Penny Dreadful Sundays',
            'hosts': ['bakert99', 'littlefield'],
            'display_time': '1:30pm Eastern',
            'time': info['pds_time'],
            'chat_room': '#PDS'
        },
        {
            'name': 'Penny Dreadful Mondays',
            'hosts': ['stash86', 'silasary'],
            'display_time': '7pm Eastern',
            'time': info['pdm_time'],
            'chat_room': '#PDM'
        },
        {
            'name': 'Penny Dreadful Thursdays',
            'hosts': ['silasary', 'stash86'],
            'display_time': '7pm Eastern',
            'time': info['pdt_time'],
            'chat_room': '#PDT'
        }
    ]
