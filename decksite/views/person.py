import json
from typing import Dict, List, Optional

import titlecase
from flask import url_for

from decksite.data import person as ps
from decksite.data.achievements import Achievement
from decksite.view import View
from magic.models import Card


# pylint: disable=no-self-use,too-many-instance-attributes
class Person(View):
    def __init__(self, person: ps.Person, cards: List[Card], season_id: Optional[int]) -> None:
        super().__init__()
        self.person = person
        self.people = [person]
        self.decks = person.decks
        self.hide_person = True
        self.cards = cards
        for record in person.head_to_head:
            record.show_record = True
            record.opp_url = url_for('person', person_id=record.opp_mtgo_username)
        self.show_head_to_head = len(person.head_to_head) > 0
        self.show_seasons = True
        self.displayed_achievements = [{'title': a.title, 'detail': titlecase.titlecase(a.display(self.person))} for a in Achievement.all_achievements if a.display(self.person)]
        self.achievements_url = url_for('achievements')
        self.person_achievements_url = url_for('person_achievements', person_id=person.id)
        colors: Dict[str, int] = {}
        for d in self.decks:
            for c in d.colors:
                colors[c] = colors.get(c, 0) + 1
        self.charts = [
            {
                'title': 'Colors Played',
                'type': 'horizontalBar',
                'labels': json.dumps(['White', 'Blue', 'Black', 'Red', 'Green', 'Colorless']),
                'series': json.dumps([colors.get('W'), colors.get('U'), colors.get('B'), colors.get('R'), colors.get('G'), colors.get('C')]),
                'options': json.dumps({'responsive': True, 'scales': {'xAxes': [{'ticks': {'precision': 0}}]}}) # Only display whole numbers on x axis.
            }
        ]
        self.add_note_url = url_for('post_player_note')
        self.matches_url = url_for('person_matches', person_id=person.id, season_id=season_id)

    def __getattr__(self, attr):
        return getattr(self.person, attr)

    def page_title(self) -> str:
        return self.person.name
