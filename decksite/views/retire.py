from flask import url_for

from decksite.data import match
from decksite.data.form import Form
from decksite.views.league_form import LeagueForm


# pylint: disable=no-self-use
class Retire(LeagueForm):
    def __init__(self, form: Form) -> None:
        super().__init__(form)
        self.logout_url = url_for('logout', target='retire')
        if len(form.decks) == 1:
            self.show_matches = True
            self.matches = match.load_matches_by_deck(form.decks[0], should_load_decks=True)

    def page_title(self) -> str:
        return 'Retire'
