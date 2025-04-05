import datetime

from dateutil.relativedelta import FR, relativedelta

from decksite.view import View
from magic import tournaments
from magic.models import Competition
from shared import dtutil
from shared.container import Container


class Prizes(View):
    def __init__(self, competitions: list[Competition]) -> None:
        super().__init__()
        self.weeks: list[Container] = []
        weeks = split_by_week(competitions)
        for week in weeks:
            prizes: dict[str, int] = {}
            if week.end_date > dtutil.now(dtutil.WOTC_TZ):
                pass
            # Super Saturdays are paid in Play Points codes, not Cardhoarder credit, skip them for now.
            competitions = [c for c in week.get('competitions', []) if not tournaments.is_super_saturday(c)]
            for c in competitions:
                for d in c.decks:
                    prizes[d.person] = prizes.get(d.person, 0) + tournaments.prize(c, d)
            subject = f'Penny Dreadful Prizes for Week Ending {week.end_date:%b} {week.end_date.day}'
            body = '\n'.join([c.name for c in competitions]) + '\n\n'
            body += '\n'.join([f'{k} {prizes[k]}' for k in sorted(prizes) if prizes[k] > 0])
            self.weeks.append(Container({'subject': subject, 'body': body, 'n': len(competitions)}))

    def page_title(self) -> str:
        return 'Prizes'

def split_by_week(competitions: list[Competition]) -> list[Container]:
    dt = (dtutil.now(dtutil.WOTC_TZ) + relativedelta(weekday=FR(-1))).replace(hour=0, minute=0, second=0)
    weeks = []
    while True:
        week = Container()
        week.start_date = dt
        week.end_date = dt + datetime.timedelta(weeks=1) - datetime.timedelta(seconds=1)
        week.competitions = []
        while len(competitions) > 0 and competitions[0].start_date > dt:
            week.competitions = week.competitions + [competitions.pop(0)]
        weeks.append(week)
        dt = dt - datetime.timedelta(weeks=1)
        if len(competitions) == 0:
            break
    return weeks
