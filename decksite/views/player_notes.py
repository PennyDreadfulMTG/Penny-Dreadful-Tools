from decksite.view import View
from shared import dtutil


# pylint: disable=no-self-use
class PlayerNotes(View):
    def __init__(self, notes, people) -> None:
        super().__init__()
        for n in notes:
            n.display_date = dtutil.display_date(n.created_date)
        self.notes = notes
        self.people = people

    def page_title(self):
        return 'Player Notes'
