from flask import url_for

import decksite.achievements as ach
from decksite.view import View
from decksite.data import person


class Achievements(View):
    def __init__(self, mtgo_username):
        super().__init__()
        self.person_url = url_for('person', person_id=mtgo_username) if mtgo_username else None
        self.achievement_descriptions = ach.descriptions(person.load_person(mtgo_username))
        if mtgo_username:
            for desc in self.achievement_descriptions:
                desc['class'] = 'earned' if desc['detail'] else 'unearned'
