import json
from typing import Any

import inflect
import titlecase
from flask import session, url_for

from decksite import prepare
from decksite.data.archetype import Archetype
from decksite.view import View
from magic import card, oracle
from magic.models import Deck as DeckModel
from shared import fetch_tools
from shared.container import Container


class Deck(View):
    def __init__(self, d: DeckModel, matches: list[Container], person_id: int | None, discord_id: int | None, archetypes: list[Archetype]) -> None:
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
        # To allow mods to change archetype from a dropdown on this page, will be empty for non-demimods
        self.archetypes = archetypes
        costs: dict[str, int] = {}
        for ci in d.maindeck:
            c = ci.card
            if c.is_land():
                continue
            if c.mana_cost is None:
                cost = '0'
            elif next((s for s in c.mana_cost if '{X}' in s), None) is not None:
                cost = 'X'
            else:
                converted = int(float(c.cmc))
                cost = '7+' if converted >= 7 else str(converted)
            costs[cost] = ci.get('n') + costs.get(cost, 0)
        self.mv_chart = {
            'type': 'bar',
            'labels': json.dumps(['0', '1', '2', '3', '4', '5', '6', '7+', 'X']),
            'series': json.dumps([costs.get('0', 0), costs.get('1', 0), costs.get('2', 0), costs.get('3', 0), costs.get('4', 0), costs.get('5', 0), costs.get('6', 0), costs.get('7+', 0), costs.get('X', 0)]),
            'options': json.dumps({
                'indexAxis': 'x',
                'scales': {
                    'x': {
                        'grid': {
                            'display': False,
                        },
                    },
                    'y': {
                        'display': False,
                        'max': round(max(costs.values(), default=0) * 1.3),
                    },
                },
            }),
        }

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
        description = f'{archetype_s} deck by {self.person}'
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

    def sections(self) -> list[dict[str, Any]]:
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

    def creatures(self) -> list[dict[str, Any]]:
        return [entry for entry in self.deck.maindeck if entry.card.is_creature()]

    def spells(self) -> list[dict[str, Any]]:
        return [entry for entry in self.deck.maindeck if entry.card.is_spell()]

    def lands(self) -> list[dict[str, Any]]:
        return [entry for entry in self.deck.maindeck if entry.card.is_land()]

    def sideboard(self) -> list[dict[str, Any]]:
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
        cs: dict[str, int] = {}
        for entry in d.maindeck + d.sideboard:
            name = entry.name
            cs[name] = cs.get(name, 0) + entry['n']
        deck_s = '||'.join([str(v) + ' ' + card.to_mtgo_format(k).replace('"', '') for k, v in cs.items()])
        return f'https://cardhoarder.com/decks/upload?deck={fetch_tools.escape(deck_s)}'

class DeckEmbed(Deck):
    pass
