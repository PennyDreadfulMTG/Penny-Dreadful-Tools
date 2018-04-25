from flask_babel import gettext

from decksite.views.league_form import LeagueForm


# pylint: disable=no-self-use
class DeckCheck(LeagueForm):
    def __init__(self, form, person_id=None):
        super().__init__(form)
        self.person_id = person_id

    def page_title(self):
        return 'Deck Check'

    def TT_DECKLIST(self):
        return gettext('Decklist')

    def TT_ENTER_OR_UPLOAD(self):
        return gettext('Enter or upload your decklist')

    def TT_YOUR_RECENT_DECKS(self):
        return gettext('Your Recent Decks')

    def TT_CHOOSE_DECK(self):
        return gettext('Select a recent deck to start from there')

    def TT_DECKCHECK(self):
        return gettext('Check your deck')
