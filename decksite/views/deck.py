from flask import url_for
import inflect

from decksite import deck_name, league
from decksite.data import deck
from decksite.view import View
from magic import oracle
from shared import dtutil

# pylint: disable=no-self-use
class Deck(View):
    def __init__(self, d):
        self._deck = d
        self.prepare_deck(self._deck)
        self.cards = d.all_cards()
        # This is called 'decks' and not something more sane because of limitations of Mustache and our desire to use a partial for decktable.
        self.decks = deck.get_similar_decks(d)
        self.has_similar = len(self.decks) > 0
        self.matches = league.get_matches(d, True)
        for m in self.matches:
            m.display_date = dtutil.display_date(m.date)
            m.opponent_url = url_for('person', person_id=m.opponent)
            m.opponent_deck_url = url_for('decks', deck_id=m.opponent_deck_id)
            m.opponent_deck_name = deck_name.normalize(m.opponent_deck)
        if d.competition_type_name == 'League':
            d.show_omw = True
        self._deck['maindeck'].sort(key=lambda x: oracle.deck_sort(x['card']))
        self._deck['sideboard'].sort(key=lambda x: oracle.deck_sort(x['card']))

    def has_matches(self):
        return len(self.matches) > 0

    def og_title(self):
        return self._deck.name

    def og_url(self):
        return 'https://pennydreadfulmagic.com' + url_for('decks', deck_id=self._deck.id)

    def og_description(self):
        if self.archetype_name:
            p = inflect.engine()
            archetype_s = p.a(self.archetype_name).title()
        else:
            archetype_s = 'A'
        description = '{archetype_s} deck by {author}'.format(archetype_s=archetype_s, author=self.person.decode('utf-8'))
        return description

    def __getattr__(self, attr):
        return getattr(self._deck, attr)

    def subtitle(self):
        return deck_name.normalize(self._deck)

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
