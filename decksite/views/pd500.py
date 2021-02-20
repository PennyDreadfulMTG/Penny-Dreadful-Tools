from typing import List

from flask import url_for

from decksite.view import View
from magic import tournaments
from magic.models import Deck
from shared import dtutil


# pylint: disable=no-self-use
class PD500(View):
    def __init__(self, tournament_winning_decks: List[Deck]) -> None:
        super().__init__()
        people = set(d.person for d in tournament_winning_decks)
        self.people_with_byes = [{'person': person, 'url': url_for('.person', mtgo_username=person)} for person in people]
        self.people_with_byes = sorted(self.people_with_byes, key=lambda k: k['person'])
        pd500_date = tournaments.pd500_date()
        if pd500_date is None or dtutil.now() > pd500_date:
            self.date_info = 'The Penny Dreadful 500 is on the second-last Saturday of the season'
        else:
            self.date_info = 'The next Penny Dreadful 500 is on ' + dtutil.display_date_with_date_and_year(pd500_date)
        self.faqs_url = url_for('faqs')
        self.cardhoarder_loan_url = 'https://www.cardhoarder.com/free-loan-program-faq'
        self.tournaments_url = url_for('tournaments')
        self.discord_url = url_for('discord')

    def page_title(self) -> str:
        return 'The Penny Dreadful 500'
