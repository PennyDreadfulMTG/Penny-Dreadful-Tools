from decksite.view import View
from shared import dtutil


# pylint: disable=no-self-use
class Unlink(View):
    def __init__(self, people, num_affected_people: int = None) -> None:
        super().__init__()
        self.people = people
        if num_affected_people is not None:
            self.message = f'{num_affected_people} were affected'

    def page_title(self):
        return 'Unlink'
