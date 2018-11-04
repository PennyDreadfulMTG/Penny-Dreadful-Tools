from decksite.view import View


# pylint: disable=no-self-use
class EditRules(View):
    def __init__(self, num_classified, num_total, doubled_decks, mistagged_decks, rules, archetypes) -> None:
        super().__init__()
        self.num_classified = num_classified
        self.num_total = num_total
        self.doubled_decks = doubled_decks
        self.mistagged_decks = mistagged_decks
        self.rules = rules
        self.archetypes = archetypes
        self.rules.sort(key=lambda c: c.archetype_name)
        for d in self.doubled_decks:
            self.prepare_deck(d)
        for d in self.mistagged_decks:
            self.prepare_deck(d)
        self.has_doubled_decks = len(self.doubled_decks) > 0
        self.has_mistagged_decks = len(self.mistagged_decks) > 0

    def page_title(self):
        return 'Edit Rules'
