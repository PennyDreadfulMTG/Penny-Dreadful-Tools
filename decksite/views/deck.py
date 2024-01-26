from typing import Any, Dict, List, Optional

import inflect
import titlecase
from flask import session, url_for

from decksite import prepare
from decksite.view import View
from magic import card, oracle
from magic.models import Deck as DeckModel
from shared import fetch_tools
from shared.container import Container


class Deck(View):
    def __init__(self, d: DeckModel, matches: List[Container], person_id: Optional[int] = None, discord_id: Optional[int] = None) -> None:
        super().__init__()
        self.deck = d
        prepare.prepare_deck(self.deck)
        self.cards = d.all_cards()
        self.matches = matches
        self.deck['maindeck'].sort(key=lambda x: oracle.deck_sort(x.card))
        self.deck['sideboard'].sort(key=lambda x: oracle.deck_sort(x.card))
        self.edit_archetype_url = url_for('edit_archetypes')
        self.legal_formats = d.legal_formats
        self.is_in_current_run = d.is_in_current_run()
        self.person_id = person_id
        self.discord_id = discord_id
        self.is_deck_page = True

    def og_title(self) -> str:
        return self.deck.name if self.public() else '(Active League Run)'

    def og_url(self) -> str:
        return url_for('deck', deck_id=self.deck.id, _external=True)

    def og_description(self) -> str:
        if self.public() and self.archetype_name and self.reviewed:
            p = inflect.engine()
            archetype_s = titlecase.titlecase(p.a(self.archetype_name))
        else:
            archetype_s = 'A'
        description = '{archetype_s} deck by {author}'.format(archetype_s=archetype_s, author=self.person)
        return description

    def oembed_url(self) -> str:
        return url_for('deck_embed', deck_id=self.deck.id, _external=True)

    def authenticate_url(self) -> str:
        return url_for('authenticate', target=self.og_url())

    def logout_url(self) -> str:
        return url_for('logout', target=self.og_url())

    def season_id(self) -> int:
        return self.deck.season_id

    def __getattr__(self, attr: str) -> Any:
        return getattr(self.deck, attr)

    def page_title(self) -> str:
        return self.deck.name if self.public() else '(Active League Run)'

    def sections(self) -> List[Dict[str, Any]]:
        sections = []
        if self.creatures():
            sections.append({'name': 'Creatures', 'entries': self.creatures(), 'num_entries': sum([c['n'] for c in self.creatures()])})
        if self.spells():
            sections.append({'name': 'Spells', 'entries': self.spells(), 'num_entries': sum([c['n'] for c in self.spells()])})
        if self.lands():
            sections.append({'name': 'Lands', 'entries': self.lands(), 'num_entries': sum([c['n'] for c in self.lands()])})
        if self.sideboard():
            sections.append({'name': 'Sideboard', 'entries': self.sideboard(), 'num_entries': sum([c['n'] for c in self.sideboard()])})
        return sections

    def creatures(self) -> List[Dict[str, Any]]:
        return [entry for entry in self.deck.maindeck if entry.card.is_creature()]

    def spells(self) -> List[Dict[str, Any]]:
        return [entry for entry in self.deck.maindeck if entry.card.is_spell()]

    def lands(self) -> List[Dict[str, Any]]:
        return [entry for entry in self.deck.maindeck if entry.card.is_land()]

    def sideboard(self) -> List[Dict[str, Any]]:
        return self.deck.sideboard

    def public(self) -> bool:
        if not self.is_in_current_run:
            return True
        if self.person_id is None:
            return False
        if session.get('admin'):
            return True
        if session.get('demimod'):
            return True
        if self.person_id != self.deck.person_id:
            return False
        return True

    def cardhoarder_url(self) -> str:
        d = self.deck
        cs: Dict[str, int] = {}
        for entry in d.maindeck + d.sideboard:
            name = entry.name
            cs[name] = cs.get(name, 0) + entry['n']
        deck_s = '||'.join([str(v) + ' ' + card.to_mtgo_format(k).replace('"', '') for k, v in cs.items()])
        return 'https://cardhoarder.com/decks/upload?deck={deck}'.format(deck=fetch_tools.escape(deck_s))

class DeckEmbed(Deck):
    pass
