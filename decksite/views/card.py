from typing import Any

from flask import url_for

from decksite.deck_type import DeckType
from decksite.view import View
from magic import oracle, seasons
from magic.models import Card as CardContainer


class Card(View):
    def __init__(self, card: CardContainer, tournament_only: bool = False, alternate_name: str | None = None) -> None:
        super().__init__()
        self.legal_formats = ([x for x, y in card.legalities.items() if y == 'Legal'] + [x + ' (restricted)' for x, y in card.legalities.items() if y == 'Restricted'])
        self.legal_seasons = sorted(seasons.SEASONS.index(fmt.replace('Penny Dreadful ', '')) + 1 for fmt, v in card.legalities.items() if 'Penny Dreadful' in fmt and v != 'Banned')
        self.show_seasons = True
        self.show_archetype = True
        self.show_tournament_toggle = True
        self.tournament_only = self.hide_source = tournament_only
        self.public = True  # Mark this as 'public' so it can share legality section code with deck.
        self.alternate_name = alternate_name
        self.display_name = alternate_name or card.name
        self.canonical_name = card.name if alternate_name else None
        self.canonical_url = url_for('.card', name=card.name, deck_type=DeckType.TOURNAMENT.value if tournament_only else None) if alternate_name else None
        if alternate_name:
            printing = oracle.preferred_printing_for_alternate_name(card, alternate_name)
            if printing is not None:
                card.preferred_printing = str(printing.set_code)
                card.preferred_printing_system_id = str(printing.system_id)
        self.toggle_results_url = url_for('.card', name=self.display_name, deck_type=None if tournament_only else DeckType.TOURNAMENT.value)
        self.card = card
        self.cards = [self.card]

    def og_title(self) -> str:
        return str(self.display_name)

    def og_description(self) -> str:
        return f'{self.display_name} in Penny Dreadful'

    def __getattr__(self, attr: str) -> Any:
        return getattr(self.card, attr)

    def page_title(self) -> str:
        return str(self.display_name)
