from shared.database import sqlescape

from decksite.data import card
from decksite.view import View

# pylint: disable=no-self-use
class Person(View):
    def __init__(self, person):
        self.person = person
        self.decks = person.decks
        self.hide_person = True
        self.cards = card.played_cards('person_id = {person_id}'.format(person_id=sqlescape(person.id)))
        self.only_played_cards = card.only_played_by(person.id)
        self.has_only_played_cards = len(self.only_played_cards) > 0

    def __getattr__(self, attr):
        return getattr(self.person, attr)

    def subtitle(self):
        return self.person.name
