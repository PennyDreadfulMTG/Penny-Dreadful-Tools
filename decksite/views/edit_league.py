from decksite.league import Status
from decksite.view import View


# pylint: disable=no-self-use
class EditLeague(View):
    def __init__(self, status: Status) -> None:
        super().__init__()
        is_open = status == Status.OPEN
        self.status = 'open' if is_open else 'closed'
        self.action_display = 'Close' if is_open else 'Open'
        self.action = self.action_display.lower()

    def page_title(self):
        return 'Edit League'
