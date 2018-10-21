from typing import List, Dict

from flask import url_for
from flask_babel import ngettext

from decksite.data import person as ps
from decksite.view import View
from magic import tournaments
from magic.models import Card


# pylint: disable=no-self-use,too-many-instance-attributes
class Person(View):
    def __init__(self, person: ps.Person, cards: List[Card], only_played_cards: List[Card]) -> None:
        super().__init__()
        self.person = person
        self.people = [person]
        self.decks = person.decks
        self.hide_person = True
        self.cards = cards
        self.only_played_cards = only_played_cards
        self.has_only_played_cards = len(self.only_played_cards) > 0
        for record in person.head_to_head:
            record.show_record = True
            record.opp_url = url_for('person', person_id=record.opp_mtgo_username)
        self.show_head_to_head = len(person.head_to_head) > 0
        self.show_seasons = True
        self.displayed_achievements : List[Dict[str, str]] = []
        if self.person.name in [host for series in tournaments.all_series_info() for host in series['hosts']]:
            self.displayed_achievements.append({'name': 'Tournament Organizer', 'detail': 'Run a tournament for the Penny Dreadful community'})
        achievements_text = [
            ('tournament_wins', 'Tournament Winner', 'Win', 'Wins'),
            ('tournament_entries', 'Tournament Player', 'Entry', 'Entries'),
            ('perfect_runs', 'Perfect League Run', 'Perfect Run', 'Perfect Runs'),
            ('flawless_runs', 'Flawless League Run', 'Flawless Run', 'Flawless Runs'),
            ('league_entries', 'League Player', 'Entry', 'Entries'),
            ('perfect_run_crushes', 'Perfect Run Crusher', 'Crush', 'Crushes')
        ]
        achievements = person.get('achievements', {})
        for k, t, v1, vp in achievements_text:
            if k in achievements and achievements[k] > 0:
                self.displayed_achievements.append({'name':t, 'detail':ngettext(f'1 {v1}', f'%(num)d {vp}', person.achievements[k])})
        if achievements.get('completionist', 0) > 0:
            self.displayed_achievements.append({'name':'Completionist', 'detail':'Never retired a league run'})
        self.achievements_url = url_for('achievements')

    def __getattr__(self, attr):
        return getattr(self.person, attr)

    def page_title(self):
        return self.person.name
