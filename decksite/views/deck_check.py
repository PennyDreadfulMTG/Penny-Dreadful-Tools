from flask_babel import gettext

from decksite.views.decklist_form import DecklistForm


class DeckCheck(DecklistForm):
    def page_title(self) -> str:
        return 'Deck Check'

    def TT_DECKCHECK(self) -> str:
        return gettext('Check your deck')
