import datetime

from flask import url_for

from decksite import league
from decksite.view import View


# pylint: disable=no-self-use
class LeagueInfo(View):
    def __init__(self) -> None:
        super().__init__()
        self.current = league.active_league()
        self.end_date = custom_strftime('%B {S}', self.current.end_date)
        self.signup_url = url_for('signup')
        self.report_url = url_for('report')
        self.records_url = url_for('current_league')
        self.retire_url = url_for('retire')
        self.bugs_url = url_for('tournaments', _anchor='bugs')

    def page_title(self):
        return 'League'

    def discord_url(self):
        return 'https://discord.gg/Yekrz3s' # Invite directly into #league channel

def suffix(d: int) -> str:
    return 'th' if 11 <= d <= 13 else {1:'st', 2:'nd', 3:'rd'}.get(d % 10, 'th')

def custom_strftime(fmt: str, t: datetime.datetime) -> str:
    return t.strftime(fmt).replace('{S}', str(t.day) + suffix(t.day))
