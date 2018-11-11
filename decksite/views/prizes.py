import datetime
from typing import Any, Dict, List

from dateutil.relativedelta import FR, relativedelta

from decksite.data.competition import Competition
from decksite.data.person import Person
from decksite.view import View
from magic import tournaments
from shared import dtutil
from shared.container import Container


# pylint: disable=no-self-use
class Prizes(View):
    def __init__(self, competitions: List[Competition], first_runs: List[Person]) -> None:
        super().__init__()
        self.weeks: List[Container] = []
        weeks = split_by_week(competitions)
        for week in weeks:
            prizes: Dict[str, int] = {}
            if week.end_date > dtutil.now(dtutil.WOTC_TZ):
                pass
            for c in week.get('competitions', []):
                for d in c.decks:
                    prizes[d.person] = prizes.get(d.person, 0) + tournaments.prize(d)
            subject = 'Penny Dreadful Prizes for Week Ending {date:%b} {date.day}'.format(date=week.end_date)
            body = '\n'.join([c.name for c in week.get('competitions', [])]) + '\n\n'
            body += '\n'.join(['{username} {prize}'.format(username=k, prize=prizes[k]) for k in sorted(prizes) if prizes[k] > 0])
            self.weeks.append(Container({'subject': subject, 'body': body, 'n': len(week.get('competitions', []))}))
        self.months: List[Dict[str, Any]] = []
        current_competition_id = None
        for p in first_runs:
            if current_competition_id != p.competition_id:
                self.months.append({'competition_name': p.competition_name, 'people': []})
                current_competition_id = p.competition_id
            self.months[-1]['people'].append(p)

    def page_title(self) -> str:
        return 'Prizes'

def split_by_week(competitions: List[Competition]) -> List[Container]:
    dt = (dtutil.now(dtutil.WOTC_TZ) + relativedelta(weekday=FR(-1))).replace(hour=0, minute=0, second=0)
    weeks = []
    while True:
        week = Container()
        week.start_date = dt
        week.end_date = dt + datetime.timedelta(weeks=1)
        week.competitions = []
        while len(competitions) > 0 and competitions[0].start_date > dt:
            week.competitions = week.competitions + [competitions.pop(0)]
        weeks.append(week)
        dt = dt - datetime.timedelta(weeks=1)
        if len(competitions) == 0:
            break
    return weeks
