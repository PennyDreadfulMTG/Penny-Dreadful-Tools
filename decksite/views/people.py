from decksite.view import View


# pylint: disable=no-self-use
class People(View):
    def __init__(self, people):
        super().__init__()
        self.people = people

    def show_seasons(self):
        return True

    def page_title(self):
        return 'People'
