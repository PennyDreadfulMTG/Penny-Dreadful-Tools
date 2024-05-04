from decksite.form import Form
from decksite.views.decklist_form import DecklistForm


class Manabase(DecklistForm):
    def __init__(self, form: Form) -> None:
        super().__init__(form, person_id=None)
        self.output = form.output

    def page_title(self) -> str:
        return 'Experimental Manabase Generator'
