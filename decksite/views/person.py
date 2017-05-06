from decksite.view import View

# pylint: disable=no-self-use
class Person(View):
    def __init__(self, person):
        self.person = person
        self.decks = person.decks
        self.hide_person = True

    def __getattr__(self, attr):
        return getattr(self.person, attr)

    def subtitle(self):
        return self.person.name.decode('utf-8')
