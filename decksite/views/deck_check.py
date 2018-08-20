from flask_babel import gettext

from decksite.views.decklist_form import DecklistForm


# pylint: disable=no-self-use
class DeckCheck(DecklistForm):
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
