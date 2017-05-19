from decksite.view import View
from decksite import league

def suffix(d):
    return 'th' if 11<=d<=13 else {1:'st',2:'nd',3:'rd'}.get(d%10, 'th')

def custom_strftime(format, t):
    return t.strftime(format).replace('{S}', str(t.day) + suffix(t.day))

# pylint: disable=no-self-use
class LeagueInfo(View):
    current = league.active_league()
    end_date = custom_strftime('%B {S}', current.end_date)

    def subtitle(self):
        return 'League'
