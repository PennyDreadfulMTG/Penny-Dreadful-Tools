from flask import url_for

from decksite import league
from decksite.data import deck
from decksite.view import View
from shared import dtutil

# pylint: disable=no-self-use
class Deck(View):
    def __init__(self, d):
        self._deck = d
        self.decks = [d]
        self.cards = d.all_cards()
        self.similar = deck.get_similar_decks(d)
        self.has_similar = len(self.similar) > 0
        self.matches = league.get_matches(d)
        for m in self.matches:
            m.display_date = dtutil.display_date(m.date)
            m.opponent_url = url_for('person', person_id=m.opponent)
            m.opponent_deck_url = url_for('decks', deck_id=m.opponent_deck_id)

    def has_matches(self):
        return len(self.matches) > 0

    def og_title(self):
        return self._deck.name

    def og_url(self):
        return 'https://pennydreadfulmagic.com' + url_for('decks', deck_id=self._deck.id)

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

    def is_league(self):
        return self._deck.competition_id == league.get_active_competition_id()
