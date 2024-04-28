from flask import url_for

from decksite.tournament import CompetitionFlag
from decksite.view import View
from magic import tournaments
from shared import dtutil


class KickOff(View):
    def __init__(self) -> None:
        super().__init__()
        kick_off_date = tournaments.kick_off_date()
        if dtutil.now() > kick_off_date:
            self.date_info_safe = 'The Season Kick Off is on the second Saturday of the season'
        else:
            display_time = dtutil.display_date_with_date_and_year(kick_off_date)
            self.date_info_safe = f'The next Season Kick Off is on <time datetime="{kick_off_date}" data-format="dddd MMMM Do LT z">{display_time}</time>'
        self.faqs_url = url_for('faqs')
        self.cardhoarder_loan_url = 'https://cardhoarder.com/free-loan-program-faq'
        self.tournaments_url = url_for('tournaments')
        self.discord_url = url_for('discord')
        self.prizes = tournaments.kick_off_prizes()

        # Set up the "Past Winners" table
        self.past_winners = {
            'competition_flag_id': CompetitionFlag.KICK_OFF.value,
            'season_id': 0,  # We want decks from all seasons, not the current season
            'show_season_icon': True,
            'hide_top8': True,
            'show_archetype': True,
        }

    def page_title(self) -> str:
        return 'The Season Kick Off'
