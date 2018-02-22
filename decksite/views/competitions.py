from decksite.view import View


# pylint: disable=no-self-use
class Competitions(View):
    def __init__(self, competitions):
        self.competitions = competitions

    def subtitle(self):
        return 'Competitions'
