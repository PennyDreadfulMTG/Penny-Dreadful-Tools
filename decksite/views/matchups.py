from typing import Dict, List, Mapping, Optional, Union

from decksite.data.archetype import Archetype
from decksite.data.person import Person
from decksite.view import View
from magic.models import Card, Deck


# pylint: disable=no-self-use,too-many-arguments,too-many-instance-attributes
class Matchups(View):
    def __init__(self, hero: Dict[str, Union[str, int]], enemy: Dict[str, Union[str, int]], season_id: Optional[int], archetypes: List[Archetype], people: List[Person], cards: List[Card], results: Mapping[str, Union[str, int, List[int], List[Deck]]]) -> None:
        super().__init__()
        self.results = results
        if results:
            self.results['num_decks'] = len(results['hero_deck_ids']) # type: ignore
            self.results['win_percent'] = str(round((results['wins'] / (results['wins'] + results['losses'])) * 100, 1)) if results.get('wins') else ''# type: ignore
        self.criteria = [
            {'name': 'Decks Matching…', 'prefix': 'hero_', 'choices': hero},
            {'name': '… versus …', 'prefix': 'enemy_', 'choices': enemy}
        ]
        # Set up options for dropdowns, marking the right ones as selected.
        for c in self.criteria:
            c['archetypes'] = [{'name': a.name, 'id': a.id, 'selected': str(c['choices'].get('archetype_id')) == str(a.id)} for a in archetypes] # type: ignore
            c['people'] = [{'mtgo_username': p.mtgo_username.lower(), 'id': p.id, 'selected': str(c['choices'].get('person_id')) == str(p.id)} for p in people] # type: ignore
            c['cards'] = [{'name': card.name, 'selected': c['choices'].get('card') == card.name} for card in cards] # type: ignore
        self.seasons = [{'season_id': s['num'] or '', 'name': s['name'], 'selected': str(season_id) == str(s['num'])} for s in [self.all_seasons()[-1]] + self.all_seasons()[:-1]]
        self.decks = results.get('hero_decks', []) # type: ignore
        self.show_decks = len(self.decks) > 0
        self.matches = results.get('matches', [])
        self.show_matches = False
        self.search_season_id = season_id
        if self.results:
            self.hero_summary = summary_text(hero, archetypes, people)
            self.enemy_summary = summary_text(enemy, archetypes, people)
            self.season_summary = f'Season {season_id}' if season_id else 'All Time'

    def show_legal_seasons(self) -> bool:
        return not self.search_season_id

    def page_title(self) -> str:
        return 'Matchups Calculator'


def summary_text(choices: Dict[str, Union[str, int]], archetypes: List[Archetype], people: List[Person]) -> str:
    s = ''
    if choices.get('archetype_id'):
        s += next(a.name for a in archetypes if a.id == int(choices['archetype_id'])) + ', '
    if choices.get('person_id'):
        s += next(p.name for p in people if p.id == int(choices['person_id'])) + ', '
    if choices.get('card'):
        s += str(choices['card']) + ', '
    s = s.strip(', ')
    if not s:
        s = 'All Decks'
    return s
