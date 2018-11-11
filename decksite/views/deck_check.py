from flask_babel import gettext

from decksite.views.decklist_form import DecklistForm


# pylint: disable=no-self-use
class DeckCheck(DecklistForm):
    def page_title(self) -> str:
        return 'Deck Check'

    def TT_DECKLIST(self) -> str:
        return gettext('Decklist')

    def TT_ENTER_OR_UPLOAD(self) -> str:
        return gettext('Enter or upload your decklist')

    def TT_YOUR_RECENT_DECKS(self) -> str:
        return gettext('Your Recent Decks')

    def TT_CHOOSE_DECK(self) -> str:
        return gettext('Select a recent deck to start from there')

    def TT_DECKCHECK(self) -> str:
        return gettext('Check your deck')
