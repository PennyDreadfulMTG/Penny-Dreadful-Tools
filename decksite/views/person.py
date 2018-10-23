from typing import Dict, List

from flask import url_for

from decksite import achievements as ach
from decksite.data import person as ps
from decksite.view import View
from magic.models import Card


# pylint: disable=no-self-use,too-many-instance-attributes
class Person(View):
    def __init__(self, person: ps.Person, cards: List[Card], only_played_cards: List[Card]) -> None:
        super().__init__()
        self.person = person
        self.people = [person]
        self.decks = person.decks
        self.hide_person = True
        self.cards = cards
        self.only_played_cards = only_played_cards
        self.has_only_played_cards = len(self.only_played_cards) > 0
        for record in person.head_to_head:
            record.show_record = True
            record.opp_url = url_for('person', person_id=record.opp_mtgo_username)
        self.show_head_to_head = len(person.head_to_head) > 0
        self.show_seasons = True
        self.displayed_achievements: List[Dict[str, str]] = ach.displayed_achievements(self.person)
        self.achievements_url = url_for('achievements')

    def __getattr__(self, attr):
        return getattr(self.person, attr)

    def page_title(self):
        return self.person.name
