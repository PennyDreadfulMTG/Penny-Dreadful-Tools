from flask import url_for

from magic import oracle
from decksite.view import View

# pylint: disable=no-self-use
class Bugs(View):
    def __init__(self):
        self.cards = oracle.bugged_cards()
        self.tournament_bugs_url = url_for('tournaments', _anchor='bugs')

    def subtitle(self):
        return 'Bugged Cards'
