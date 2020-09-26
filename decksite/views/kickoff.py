from flask import url_for

from decksite.view import View
from magic import tournaments
from shared import dtutil


# pylint: disable=no-self-use
class KickOff(View):
    def __init__(self) -> None:
        super().__init__()
        kick_off_date = tournaments.kick_off_date()
        if dtutil.now() > kick_off_date:
            self.date_info = 'The Season Kick Off is on the second Saturday of the season'
        else:
            self.date_info = 'The next Season Kick Off is on ' + dtutil.display_date_with_date_and_year(kick_off_date)
        self.faqs_url = url_for('faqs')
        self.cardhoarder_loan_url = 'https://www.cardhoarder.com/free-loan-program-faq'
        self.tournaments_url = url_for('tournaments')
        self.discord_url = url_for('discord')

    def page_title(self) -> str:
        return 'The Season Kick Off'
