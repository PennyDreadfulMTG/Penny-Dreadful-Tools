from decksite.view import View


# pylint: disable=no-self-use
class People(View):
    def __init__(self, people) -> None:
        super().__init__()
        self.people = people
        self.show_seasons = True

    def page_title(self):
        return 'People'
