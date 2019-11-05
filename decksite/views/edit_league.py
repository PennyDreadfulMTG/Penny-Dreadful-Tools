from decksite.view import View


# pylint: disable=no-self-use
class EditLeague(View):
    def __init__(self, is_open: bool) -> None:
        super().__init__()
        self.status = 'open' if is_open else 'closed'
        self.action_display = 'Close' if is_open else 'Open'
        self.action = self.action_display.lower()

    def page_title(self):
        return 'Edit League'
