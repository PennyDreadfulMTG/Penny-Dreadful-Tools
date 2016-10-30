from decksite.view import View

# pylint: disable=no-self-use
class Person(View):
    def __init__(self, person):
        self.person = person

    def __getattr__(self, attr):
        return getattr(self.person, attr)

    def subtitle(self):
        return self.person.name
