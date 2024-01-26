from typing import List

from flask import url_for

from decksite.view import View
from magic import tournaments
from magic.models import Deck
from shared import dtutil


class PD500(View):
    def __init__(self, tournament_winning_decks: List[Deck]) -> None:
        super().__init__()
        people = set(d.person for d in tournament_winning_decks)
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

    def page_title(self) -> str:
        return 'The Penny Dreadful 500'
