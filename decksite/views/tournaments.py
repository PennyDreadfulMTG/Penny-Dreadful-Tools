from dateutil import rrule

from shared import dtutil

from decksite.view import View

# pylint: disable=no-self-use
class Tournaments(View):
    def __init__(self):
        now = dtutil.now(dtutil.GATHERLING_TZ)
        now_ts = dtutil.dt2ts(dtutil.now())
        pdm_time = rrule.rrule(rrule.WEEKLY, byhour=19, byminute=0, bysecond=0, dtstart=now, byweekday=rrule.MO)[0]
        pdt_time = rrule.rrule(rrule.WEEKLY, byhour=19, byminute=0, bysecond=0, dtstart=now, byweekday=rrule.TH)[0]
        pds_time = rrule.rrule(rrule.WEEKLY, byhour=13, byminute=30, bysecond=0, dtstart=now, byweekday=rrule.SU)[0]
        if pdm_time < pdt_time and pdm_time < pds_time:
            self.next_tournament_name = 'Penny Dreadful Monday'
            next_time = pdm_time
        elif pdt_time < pds_time:
            self.next_tournament_name = 'Penny Dreadful Thursday'
            next_time = pdt_time
        else:
            self.next_tournament_name = 'Penny Dreadful Sunday'
            next_time = pds_time
        self.next_tournament_time = dtutil.display_time(dtutil.dt2ts(next_time) - now_ts, granularity=1)
        self.tournaments = [
            {
                'name': 'Penny Dreadful Mondays',
                'host': 'stash86',
                'display_time': '7pm Eastern',
                'time': pdm_time,
                'chat_room': '#PDM'
            },
            {
                'name': 'Penny Dreadful Thursdays',
                'host': 'silasary',
                'display_time': '7pm Eastern',
                'time': pdt_time,
                'chat_room': '#PDT'
            },
            {
                'name': 'Penny Dreadful Sundays',
                'host': 'bakert99',
                'display_time': '1:30pm Eastern',
                'time': pds_time,
                'chat_room': '#PDS'
            }
        ]

    def subtitle(self):
        return 'Tournaments'
