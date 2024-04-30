from flask import url_for

from decksite.tournament import CompetitionFlag
from decksite.view import View
from magic import tournaments
from magic.models import Deck
from shared import dtutil


class PD500(View):
    def __init__(self, tournament_winning_decks: list[Deck]) -> None:
        super().__init__()
        people = {d.person for d in tournament_winning_decks}
        self.people_with_byes = [{'person': person, 'url': url_for('.person', mtgo_username=person)} for person in people]
        self.people_with_byes = sorted(self.people_with_byes, key=lambda k: k['person'])
        pd500_date = tournaments.pd500_date()
        if dtutil.now() > pd500_date:
            self.date_info_safe = 'The Penny Dreadful 500 is on the last Saturday of the season'
        else:
            display_time = dtutil.display_date_with_date_and_year(pd500_date)
            self.date_info_safe = f'The next Penny Dreadful 500 is on <time datetime="{pd500_date}" data-format="dddd MMMM Do LT z">{display_time}</time>'
        self.faqs_url = url_for('faqs')
        self.cardhoarder_loan_url = 'https://cardhoarder.com/free-loan-program-faq'
        self.tournaments_url = url_for('tournaments')
        self.discord_url = url_for('discord')
        self.prizes = tournaments.pd500_prizes()

        # Set up the "Past Winners" table
        self.past_winners = {
            'competition_flag_id': CompetitionFlag.PENNY_DREADFUL_500.value,
            'season_id': 0,  # We want decks from all seasons, not the current season
            'show_season_icon': True,
            'hide_top8': True,
            'show_archetype': True,
        }

    def page_title(self) -> str:
        return 'The Penny Dreadful 500'
