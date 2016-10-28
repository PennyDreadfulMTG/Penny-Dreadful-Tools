from decksite.view import View

# pylint: disable=no-self-use
class Deck(View):
    def __init__(self, deck):
        self._deck = deck

    def __getattr__(self, attr):
        return getattr(self._deck, attr)

    def subtitle(self):
        return self._deck.name

    def sections(self):
        sections = []
        if self.creatures():
            sections.append({'name': 'Creatures', 'entries': self.creatures()})
        if self.spells():
            sections.append({'name': 'Spells', 'entries': self.spells()})
        if self.lands():
            sections.append({'name': 'Lands', 'entries': self.lands()})
        if self.sideboard():
            sections.append({'name': 'Sideboard', 'entries': self.sideboard()})
        return sections

    def creatures(self):
        return [entry for entry in self._deck.maindeck if entry['card'].is_creature()]

    def spells(self):
        return [entry for entry in self._deck.maindeck if entry['card'].is_spell()]

    def lands(self):
        return [entry for entry in self._deck.maindeck if entry['card'].is_land()]

    def sideboard(self):
        return self._deck.sideboard
