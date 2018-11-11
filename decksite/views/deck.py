from typing import Any, Dict, Optional

import inflect
import titlecase
from flask import session, url_for

from decksite.data import archetype, deck, match
from decksite.view import View
from magic import card, fetcher, oracle
from shared import dtutil
from shared.container import Container
from shared.pd_exception import InvalidDataException


# pylint: disable=no-self-use, too-many-instance-attributes
class Deck(View):
    def __init__(self, d: deck.Deck, person_id: Optional[int] = None, discord_id: Optional[int] = None) -> None:
        super().__init__()
        self.deck = d
        self.prepare_deck(self.deck)
        self.cards = d.all_cards()
        if not self.deck.is_in_current_run():
            deck.load_similar_decks([d])
            # This is called 'decks' and not something more sane because of limitations of Mustache and our desire to use a partial for decktable.
            self.decks = [sd for sd in d.similar_decks if not sd.is_in_current_run()]
        else:
            self.decks = []
        self.has_similar = len(self.decks) > 0
        self.matches = match.get_matches(d, True)
        for m in self.matches:
            m.display_date = dtutil.display_date(m.date)
            if m.opponent:
                m.opponent_url = url_for('person', person_id=m.opponent)
            else:
                m.opponent = 'BYE'
                m.opponent_url = False
            if m.opponent_deck_id:
                m.opponent_deck_url = url_for('deck', deck_id=m.opponent_deck_id)
            else:
                m.opponent_deck_url = False
            if m.opponent_deck and m.opponent_deck.is_in_current_run():
                m.opponent_deck_name = '(Active League Run)'
            elif m.opponent_deck:
                m.opponent_deck_name = m.opponent_deck.name
            else:
                m.opponent_deck_name = '-'
            if self.has_rounds():
                m.display_round = display_round(m)
        self.deck['maindeck'].sort(key=lambda x: oracle.deck_sort(x.card))
        self.deck['sideboard'].sort(key=lambda x: oracle.deck_sort(x.card))
        self.archetypes = archetype.load_archetypes_deckless(order_by='a.name')
        self.edit_archetype_url = url_for('edit_archetypes')
        self.legal_formats = d.legal_formats
        self.is_in_current_run = d.is_in_current_run()
        self.person_id = person_id
        self.discord_id = discord_id

    def has_matches(self) -> bool:
        return len(self.matches) > 0

    def has_rounds(self) -> bool:
        return self.has_matches() and self.matches[0].get('round')

    def og_title(self) -> str:
        return self.deck.name if self.public() else '(Active League Run)'

    def og_url(self) -> str:
        return url_for('deck', deck_id=self.deck.id, _external=True)

    def og_description(self) -> str:
        if self.public() and self.archetype_name:
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

    def __getattr__(self, attr: str) -> Any:
        return getattr(self.deck, attr)

    def page_title(self) -> str:
        return self.deck.name if self.public() else '(Active League Run)'

    def sections(self):
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

    def creatures(self):
        return [entry for entry in self.deck.maindeck if entry.card.is_creature()]

    def spells(self):
        return [entry for entry in self.deck.maindeck if entry.card.is_spell()]

    def lands(self):
        return [entry for entry in self.deck.maindeck if entry.card.is_land()]

    def sideboard(self):
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

    def cardhoarder_url(self) -> str: # This should be a Deck, but we can't import it from here.
        d = self.deck
        cs: Dict[str, int] = {}
        for entry in d.maindeck + d.sideboard:
            name = entry.name
            cs[name] = cs.get(name, 0) + entry['n']
        deck_s = '||'.join([str(v) + ' ' + card.to_mtgo_format(k).replace('"', '') for k, v in cs.items()])
        return 'https://www.cardhoarder.com/decks/upload?deck={deck}'.format(deck=fetcher.internal.escape(deck_s))

def display_round(m: Container) -> str:
    if not m.get('elimination'):
        return m.round
    if int(m.elimination) == 8:
        return 'QF'
    if int(m.elimination) == 4:
        return 'SF'
    if int(m.elimination) == 2:
        return 'F'
    raise InvalidDataException('Do not recognize round in {m}'.format(m=m))

class DeckEmbed(Deck):
    pass
