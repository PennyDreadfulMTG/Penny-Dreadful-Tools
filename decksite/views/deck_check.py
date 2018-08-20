from flask_babel import gettext

from decksite.views.league_form import LeagueForm


# pylint: disable=no-self-use
class DeckCheck(LeagueForm):
    def __init__(self, form, person_id: int = None) -> None:
        super().__init__(form)
        self.person_id = person_id
        self.classify_illegal_cards()

    def classify_illegal_cards(self) -> None:
        if self.form.card_errors is not None:
            self.has_not_legal = 'Legality_Not_Legal' in self.form.card_errors and len(self.form.card_errors['Legality_Not_Legal']) > 0
            self.has_banned = 'Legality_Banned' in self.form.card_errors and len(self.form.card_errors['Legality_Banned']) > 0
            self.has_bugs = 'Legality_Bugs' in self.form.card_errors and len(self.form.card_errors['Legality_Bugs']) > 0
            self.has_too_many = 'Legality_Too_Many' in self.form.card_errors and len(self.form.card_errors['Legality_Too_Many']) > 0

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
