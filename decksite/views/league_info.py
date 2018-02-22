from flask import url_for
from flask_babel import gettext

from decksite import league, localization
from decksite.view import View


# pylint: disable=no-self-use
class LeagueInfo(View):
    def __init__(self):
        self.current = league.active_league()
        self.end_date = custom_strftime('%B {S}', self.current.end_date)
        self.signup_url = url_for('signup')
        self.report_url = url_for('report')
        self.records_url = url_for('current_league')
        self.retire_url = url_for('retire')

    def subtitle(self):
        return 'League'

    # By doing it this way, all we need to care about is the text left, inside, and right of the link.
    def TT_LEAGUE_LASTS_A_MONTH(self):
        return gettext('Each league lasts roughly a month. The [[current league]] will run until {END_DATE}.').format(END_DATE=self.end_date)

    def TT_LEAGUE_LASTS_A_MONTH_1(self):
        return localization.split_link(self.TT_LEAGUE_LASTS_A_MONTH())[0]

    def TT_LEAGUE_LASTS_A_MONTH_2(self):
        return localization.split_link(self.TT_LEAGUE_LASTS_A_MONTH())[1]

    def TT_LEAGUE_LASTS_A_MONTH_3(self):
        return localization.split_link(self.TT_LEAGUE_LASTS_A_MONTH())[2]

    def TT_SIGNUP_AT_ANY_TIME(self):
        return gettext('You can [[sign up]] at any time.')

    def TT_SIGNUP_AT_ANY_TIME_1(self):
        return localization.split_link(self.TT_SIGNUP_AT_ANY_TIME())[0]

    def TT_SIGNUP_AT_ANY_TIME_2(self):
        return localization.split_link(self.TT_SIGNUP_AT_ANY_TIME())[1]

    def TT_SIGNUP_AT_ANY_TIME_3(self):
        return localization.split_link(self.TT_SIGNUP_AT_ANY_TIME())[2]

def suffix(d):
    return 'th' if 11 <= d <= 13 else {1:'st', 2:'nd', 3:'rd'}.get(d % 10, 'th')

def custom_strftime(fmt, t):
    return t.strftime(fmt).replace('{S}', str(t.day) + suffix(t.day))
