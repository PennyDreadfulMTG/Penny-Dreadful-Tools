from collections.abc import Mapping

from decksite.data.archetype import Archetype
from decksite.data.matchup import MatchupResults
from decksite.data.person import Person
from decksite.view import View
from magic.models import Card


class Matchups(View):
    def __init__(self, hero: Mapping[str, str | int], enemy: Mapping[str, str | int], season_id: int | None, archetypes: list[Archetype], people: list[Person], cards: list[Card], results: MatchupResults | None) -> None:
        super().__init__()
        self.results = results
        self.criteria = [
            {'name': 'Decks Matching…', 'prefix': 'hero_', 'choices': hero},
            {'name': '… versus …', 'prefix': 'enemy_', 'choices': enemy},
        ]
        # Set up options for dropdowns, marking the right ones as selected.
        for c in self.criteria:
            c['archetypes'] = [{'name': a.name, 'id': a.id, 'selected': str(c['choices'].get('archetype_id')) == str(a.id)} for a in archetypes]  # type: ignore
            c['people'] = [{'mtgo_username': p.mtgo_username.lower(), 'id': p.id, 'selected': str(c['choices'].get('person_id')) == str(p.id)} for p in people]  # type: ignore
            c['cards'] = [{'name': card.name, 'selected': c['choices'].get('card') == card.name} for card in cards]  # type: ignore
        self.seasons = [{'season_id': s['num'] or '', 'name': s['name'], 'selected': str(season_id) == str(s['num'])} for s in [self.all_seasons()[-1]] + self.all_seasons()[:-1]]
        self.decks = results.hero_decks if results and results.hero_decks else []
        self.show_decks = len(self.decks) > 0
        self.matches = results.matches if results and results.matches else []
        self.show_matches = len(self.matches) > 0
        self.hero_summary = summary_text(hero, archetypes, people)
        self.enemy_summary = summary_text(enemy, archetypes, people)
        self.season_summary = f'Season {season_id}' if season_id else 'All Time'
        self.show_hero = True  # We should show both players in the list of matches, not just "opponent".
        self.search_season_id = season_id

    def show_season_icon(self) -> bool:
        return not self.search_season_id

    def page_title(self) -> str:
        return 'Matchups Calculator'


def summary_text(choices: Mapping[str, str | int], archetypes: list[Archetype], people: list[Person]) -> str:
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
