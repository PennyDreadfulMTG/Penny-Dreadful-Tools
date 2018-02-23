import inflect
import titlecase
from flask import session, url_for

from decksite.data import archetype, deck, match
from decksite.view import View
from magic import fetcher, legality, oracle
from shared import dtutil
from shared.pd_exception import InvalidDataException


# pylint: disable=no-self-use, too-many-instance-attributes
class Deck(View):
    def __init__(self, d, logged_person_id=None):
        self._deck = d
        self.prepare_deck(self._deck)
        self.cards = d.all_cards()
        if not self._deck.is_in_current_run():
            # This is called 'decks' and not something more sane because of limitations of Mustache and our desire to use a partial for decktable.
            self.decks = [sd for sd in deck.get_similar_decks(d) if not sd.is_in_current_run()]
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
            if m.opponent_deck:
                m.opponent_deck_name = m.opponent_deck.name
            else:
                m.opponent_deck_name = '-'
            if self.has_rounds():
                m.display_round = display_round(m)
        self._deck['maindeck'].sort(key=lambda x: oracle.deck_sort(x['card']))
        self._deck['sideboard'].sort(key=lambda x: oracle.deck_sort(x['card']))
        self.archetypes = archetype.load_archetypes_deckless(order_by='a.name')
        self.edit_archetype_url = url_for('edit_archetypes')
        self.cardhoarder_url = fetcher.cardhoarder_url(d)
        self.legal_formats = list(sorted(d.legal_formats, key=legality.order_score))
        self.is_in_current_run = d.is_in_current_run()
        self.logged_person_id = logged_person_id

    def has_matches(self):
        return len(self.matches) > 0

    def has_rounds(self):
        return self.has_matches() and self.matches[0].get('round')

    def og_title(self):
        return self._deck.name

    def og_url(self):
        return url_for('deck', deck_id=self._deck.id, _external=True)

    def og_description(self):
        if self.archetype_name:
            p = inflect.engine()
            archetype_s = titlecase.titlecase(p.a(self.archetype_name))
        else:
            archetype_s = 'A'
        description = '{archetype_s} deck by {author}'.format(archetype_s=archetype_s, author=self.person.decode('utf-8'))
        return description

    def authenticate_url(self):
        return url_for('authenticate', target=self.og_url())

    def logout_url(self):
        return url_for('logout', target=self.og_url())

    def __getattr__(self, attr):
        return getattr(self._deck, attr)

    def subtitle(self):
        return self._deck.name

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
        return [entry for entry in self._deck.maindeck if entry['card'].is_creature()]

    def spells(self):
        return [entry for entry in self._deck.maindeck if entry['card'].is_spell()]

    def lands(self):
        return [entry for entry in self._deck.maindeck if entry['card'].is_land()]

    def sideboard(self):
        return self._deck.sideboard

    def public(self):
        if not self.is_in_current_run:
            return True
        if self.logged_person_id is None:
            return False
        if session.get('admin'):
            return True
        if self.logged_person_id != self._deck.person_id:
            return False
        return True

def display_round(m):
    if not m.get('elimination'):
        return m.round
    if int(m.elimination) == 8:
        return 'QF'
    elif int(m.elimination) == 4:
        return 'SF'
    elif int(m.elimination) == 2:
        return 'F'
    else:
        raise InvalidDataException('Do not recognize round in {m}'.format(m=m))
