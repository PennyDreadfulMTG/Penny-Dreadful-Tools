from typing import Dict, List, Optional, Union

from decksite.data.archetype import Archetype
from decksite.data.person import Person
from decksite.view import View
from magic.models import Card


# pylint: disable=no-self-use,too-many-arguments
class Matchups(View):
    def __init__(self, hero: Dict[str, Union[str, int]], enemy: Dict[str, Union[str, int]], season_id: Optional[int], archetypes: List[Archetype], people: List[Person], cards: List[Card], results: Dict[str, Union[str, int, List[int]]]) -> None:
        super().__init__()
        self.results = results
        self.results['num_decks'] = len(results['hero_deck_ids']) # type: ignore
        if results['wins']:
            self.results['win_percent'] = str(round((results['wins'] / (results['wins'] + results['losses'])) * 100, 1)) # type: ignore
        else:
            self.results['win_percent'] = ''
        self.criteria = [
            {'n': 1, 'prefix': 'hero_', 'choices': hero},
            {'n': 2, 'prefix': 'enemy_', 'choices': enemy}
        ]
        # Set up options for dropdowns, marking the right ones as selected.
        for c in self.criteria:
            c['archetypes'] = [{'name': a.name, 'id': a.id, 'selected': str(c['choices'].get('archetype_id')) == str(a.id)} for a in archetypes] # type: ignore
            c['people'] = [{'mtgo_username': p.mtgo_username, 'id': p.id, 'selected': str(c['choices'].get('person_id')) == str(p.id)} for p in people] # type: ignore
            c['cards'] = [{'name': card.name, 'selected': c['choices'].get('card') == card.name} for card in cards] # type: ignore
        self.seasons = [{'season_id': s['num'] or '', 'name': s['name'], 'selected': str(season_id) == str(s['num'])} for s in self.all_seasons()]
