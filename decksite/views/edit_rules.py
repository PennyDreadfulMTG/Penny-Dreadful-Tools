from flask import url_for

from decksite.data.archetype import Archetype
from decksite.view import View
from magic.models import Deck
from shared.container import Container


class EditRules(View):
    def __init__(self,
                 num_classified: int,
                 num_total: int,
                 doubled_decks: list[Deck],
                 mistagged_decks: list[Deck],
                 overlooked_decks: list[Deck],
                 rules: list[Container],
                 archetypes: list[Archetype],
                 excluded_archetype_info: list[Container]) -> None:
        super().__init__()
        self.num_classified = num_classified
        self.num_total = num_total
        self.doubled_decks = doubled_decks[0:100]
        self.mistagged_decks = mistagged_decks[0:100]
        self.overlooked_decks = overlooked_decks[0:10]
        self.rules = rules
        self.archetypes = archetypes
        archetypes_with_rules = {rule.archetype_id for rule in rules}
        self.leaf_nodes_with_no_rule = ', '.join(archetype.name for archetype in archetypes if not archetype.children and archetype.id not in archetypes_with_rules)
        self.rules.sort(key=lambda c: c.archetype_name)
        for r in self.rules:
            r.included_cards_s = '\n'.join('{n} {card}'.format(n=entry['n'], card=entry['card']) for entry in r.included_cards)
            r.excluded_cards_s = '\n'.join('{n} {card}'.format(n=entry['n'], card=entry['card']) for entry in r.excluded_cards)
        self.decks = self.doubled_decks + self.mistagged_decks + self.overlooked_decks
        for d in self.mistagged_decks:
            d.rule_archetype_url = url_for('.archetype', archetype_id=d.rule_archetype_name)
        for d in self.doubled_decks:
            for a in d.archetypes_from_rules:
                a.archetype_url = url_for('.archetype', archetype_id=a.archetype_id)
        self.has_doubled_decks = len(self.doubled_decks) > 0
        self.has_mistagged_decks = len(self.mistagged_decks) > 0
        self.has_overlooked_decks = len(self.overlooked_decks) > 0
        self.hide_active_runs = False
        for ai in excluded_archetype_info:
            ai.url = url_for('.archetype', archetype_id=ai.id)
        self.excluded_archetypes = excluded_archetype_info
        self.has_excluded_archetypes = len(self.excluded_archetypes) > 0

    def page_title(self) -> str:
        return 'Edit Rules'
