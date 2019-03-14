import copy
from typing import Dict, List, Optional, Union

from decksite.data.archetype import Archetype
from decksite.data.person import Person
from decksite.view import View
from magic.models import Card
from shared.container import Container


# pylint: disable=no-self-use
class Matchups(View):
    def __init__(self, hero: Dict[str, Union[str, int]], enemy: Dict[str, Union[str, int]], season_id: Optional[int], archetypes: List[Archetype], people: List[Person], cards: List[Card], results: Dict[str, Union[str, int]]) -> None:
        super().__init__()
        self.results = results
        self.criteria = [
            {'n': 1, 'prefix': 'hero_', 'selected': hero},
            {'n': 2, 'prefix': 'enemy_', 'selected': enemy}
        ]
        # Set up options for dropdowns, marking the right ones as selected.
        for c in self.criteria:
            c['archetypes'] = [{'name': a.name, 'id': a.id, 'selected': str(c['selected'].get('archetype_id')) == str(a.id)} for a in archetypes]
            c['people'] = [{'mtgo_username': p.mtgo_username, 'id': p.id, 'selected': str(c['selected'].get('person_id')) == str(p.id)} for p in people]
            c['cards'] = [{'name': card.name, 'selected': c['selected'].get('card') == card.name} for card in cards]
        self.seasons = self.all_seasons()
        for s in self.seasons:
            if str(season_id) == str(s['num']):
                s['selected'] = True
