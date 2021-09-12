from typing import Dict, List

from flask import url_for

from decksite.data.archetype import Archetype
from decksite.deck_type import DeckType
from decksite.view import View
from magic import image_fetcher, oracle

LEFT_PADDING = 2
TOTAL_HEIGHT = 20000


# pylint: disable=no-self-use
class Metagame(View):
    def __init__(self, archetypes: List[Archetype], tournament_only: bool, key_cards: Dict[int, str]) -> None:
        super().__init__()

        self.decks = []
        self.show_seasons = True
        self.tournament_only = self.hide_perfect_runs = tournament_only
        self.show_tournament_toggle = True
        self.toggle_results_url = url_for('.metagame', deck_type=None if tournament_only else DeckType.TOURNAMENT.value)

        self.archetypes = []
        total_matches = sum([(a.wins or 0) + (a.losses or 0) + (a.draws or 0) for a in archetypes])
        for a in archetypes:
            card = key_cards.get(a.id)
            a.num_matches = (a.wins or 0) + (a.losses or 0) + (a.draws or 0)
            if a.num_matches > 0:
                a.display_width = max(float(a.win_percent) - LEFT_PADDING if a.win_percent else 0, 0)
                a.display_height = a.num_matches / total_matches * TOTAL_HEIGHT
                a.font_size = min(a.display_height / 2, 20)
                if card:
                    url = image_fetcher.scryfall_image(oracle.load_card(card), 'art_crop')
                    a.background = f'linear-gradient(0deg, rgba(0,0,0,0.2), rgba(0,0,0,0.2)), url({url}) center top / cover no-repeat'
                else:
                    a.background = '#ccc'
                if not a.is_leaf:
                    a.name = f'Other {a.name}'
                a.num_matches_plural = 'es' if a.num_matches != 1 else ''
                self.archetypes.append(a)
        self.archetypes.sort(key=lambda o: o.display_width, reverse=True)

    def page_title(self) -> str:
        return 'Metagame'
