from typing import Dict, List, Union

from decksite.data.archetype import Archetype
from decksite.data.person import Person
from decksite.view import View
from magic.models import Card


# pylint: disable=no-self-use
class Matchups(View):
    def __init__(self, archetypes: List[Archetype], people: List[Person], cards: List[Card], results: Dict[str, Union[str, int]]) -> None:
        super().__init__()
        self.archetypes = archetypes
        self.people = people
        self.cards = cards
        self.results = results
        self.criteria = [
            {'n': 1, 'prefix': 'hero_'},
            {'n': 2, 'prefix': 'enemy_'}
        ]
