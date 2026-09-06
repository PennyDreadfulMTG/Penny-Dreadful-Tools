from collections.abc import Mapping

from decksite.data.matchup import MatchupResults
from decksite.view import View


class Matchups(View):
    def __init__(self, hero: Mapping[str, str | int], enemy: Mapping[str, str | int], season_id: int | None, results: MatchupResults | None) -> None:
        super().__init__()
        self.results = results
        self.criteria = [
            criterion('Decks Matching…', 'hero_', hero),
            criterion('… versus …', 'enemy_', enemy),
        ]
        self.seasons = [{'season_id': s['num'] or '', 'name': s['name'], 'selected': str(season_id) == str(s['num'])} for s in self.all_seasons()]
        self.decks = results.hero_decks if results and results.hero_decks else []
        self.show_decks = len(self.decks) > 0
        self.matches = results.matches if results and results.matches else []
        self.show_matches = len(self.matches) > 0
        self.hero_summary = summary_text(hero)
        self.enemy_summary = summary_text(enemy)
        self.season_summary = f'Season {season_id}' if season_id else 'All Time'
        self.show_hero = True  # We should show both players in the list of matches, not just "opponent".
        self.search_season_id = season_id

    def show_season_icon(self) -> bool:
        return not self.search_season_id

    def page_title(self) -> str:
        return 'Matchups Calculator'


def summary_text(choices: Mapping[str, str | int]) -> str:
    parts = [str(choices[k]) for k in ('archetype_name', 'person_name', 'card') if choices.get(k)]
    return ', '.join(parts) or 'All Decks'


def criterion(name: str, prefix: str, choices: Mapping[str, str | int]) -> dict[str, object]:
    return {
        'name': name,
        'prefix': prefix,
        'archetype_id': choices.get('archetype_id') or '',
        'archetype_name': choices.get('archetype_name') or '',
        'person_id': choices.get('person_id') or '',
        'person_label': choices.get('person_label') or '',
        'card': choices.get('card') or '',
    }
