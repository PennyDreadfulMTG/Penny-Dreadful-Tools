from decksite.view import View


# pylint: disable=no-self-use
class Competitions(View):
    def __init__(self, competitions):
        super().__init__()
        self.competitions = competitions

    def subtitle(self):
        return 'Competitions'
