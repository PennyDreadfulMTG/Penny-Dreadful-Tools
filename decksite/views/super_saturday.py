from flask import url_for

from decksite.tournament import CompetitionFlag
from decksite.view import View
from magic import tournaments
from shared import dtutil


class SuperSaturday(View):
    def __init__(self) -> None:
        super().__init__()
        super_saturday_date = tournaments.super_saturday_date()
        if dtutil.now() > super_saturday_date:
            self.date_info_safe = 'MTGO Super Saturday was on March 29th 2025'
        else:
            display_time = dtutil.display_date_with_date_and_year(super_saturday_date)
            self.date_info_safe = f'MTGO Super Saturday is on <time datetime="{super_saturday_date}" data-format="dddd MMMM Do LT z">{display_time}</time>'
        self.faqs_url = url_for('faqs')
        self.cardhoarder_loan_url = 'https://cardhoarder.com/free-loan-program-faq'
        self.tournaments_url = url_for('tournaments')
        self.discord_url = url_for('discord')
        self.prizes = tournaments.super_saturday_prizes()

        # Set up the "Past Winners" table
        self.past_winners = {
            'competition_flag_id': CompetitionFlag.SUPER_SATURDAY.value,
            'season_id': 0,  # We want decks from all seasons, not the current season
            'show_season_icon': True,
            'hide_top8': True,
            'show_archetype': True,
        }

    def page_title(self) -> str:
        return 'MTGO Super Saturday'
