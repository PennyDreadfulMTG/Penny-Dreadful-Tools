import inflect
from flask import url_for

from magic import tournaments
from shared import rules

from decksite.data import competition
from decksite.view import View

# pylint: disable=no-self-use
class Tournaments(View):
    def __init__(self):

        info = tournaments.next_tournament_info()
        self.next_tournament_name = info['next_tournament_name']
        self.next_tournament_time = info['next_tournament_time']
        self.leaderboards_url = url_for('tournament_leaderboards')

        self.tournaments = sorted(tournaments.all_series_info(), key=lambda t: t.time)
        leagues = competition.load_competitions("c.competition_series_id IN (SELECT id FROM competition_series WHERE name = 'League') AND c.end_date > UNIX_TIMESTAMP(NOW())")
        end_date, prev_month, shown_end = None, None, False
        for t in self.tournaments:
            month = t.time.strftime('%b')
            if month != prev_month:
                t.month = month
                prev_month = month
            t.date = t.time.strftime('%-d')
            if len(leagues) > 0 and t.time >= leagues[-1].start_date and t.time < leagues[-1].end_date:
                t.league = leagues.pop(-1)
                t.league.display = True
                end_date = t.league.end_date
            elif not shown_end and end_date and t.time >= end_date:
                t.league = {'class': 'begin', 'display': False}
                shown_end = True
            elif end_date:
                t.league = {'class': 'ongoing', 'display': False}
        p = inflect.engine()
        self.num_tournaments = p.number_to_words(len(self.tournaments))

        self.bugs_rules = rules.bugs(fmt=rules.HTML)

    def subtitle(self):
        return 'Tournaments'
