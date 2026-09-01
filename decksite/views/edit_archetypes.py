from flask import url_for

from decksite import prepare
from decksite.data import archetype, deck, rule
from decksite.data.archetype import Archetype
from decksite.view import View


class EditArchetypes(View):
    def __init__(self, archetypes: list[Archetype], q: str, notq: str, query_errors: list[str] | None = None, notquery_errors: list[str] | None = None) -> None:
        super().__init__()
        self.archetypes = archetypes
        self.archetypes_preordered = archetype.preorder(archetypes)
        ds, _ = deck.load_decks(where='NOT d.reviewed', order_by='updated_date DESC', limit='LIMIT 20')
        self.queue = ds
        deck.load_queue_similarity(self.queue)
        rule.apply_rules_to_decks(self.queue)
        archetype_descriptions = {a.id: a.description for a in archetypes}
        for d in self.queue:
            prepare.prepare_deck(d)
            d.archetype_url = url_for('.archetype', archetype_id=d.archetype_name)
            d.archetype_description = archetype_descriptions.get(d.get('archetype_id'), '')
            if d.get('rule_archetype_id'):
                d.rule_archetype_url = url_for('.archetype', archetype_id=d.rule_archetype_name)
                d.rule_archetype_description = archetype_descriptions.get(d.rule_archetype_id, '')
                d.archetypes = []
                for a in self.archetypes:
                    if a.id == d.rule_archetype_id:
                        d.archetypes.append({'id': a.id, 'name': a.name, 'selected': True})
                    else:
                        d.archetypes.append(a)
            if d.get('rule_archetype_id') == 0:
                d.rule_archetype_url = url_for('edit_rules')
            d.show_add_rule_prompt = d.similarity == '100%' and not d.get('rule_archetype_name')
            d['prefix'] = f'{d.id}_'
        self.edit_rules_url = url_for('edit_rules')
        self.query = q
        self.notquery = notq
        self.query_errors = query_errors or []
        self.notquery_errors = notquery_errors or []
        self.has_query_errors = bool(self.query_errors)
        self.has_notquery_errors = bool(self.notquery_errors)

    def page_title(self) -> str:
        return 'Edit Archetypes'
