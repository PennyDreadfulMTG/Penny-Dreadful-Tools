from flask import url_for

import decksite.achievements as ach
from decksite.view import View


class Achievements(View):
    def __init__(self, mtgo_username):
        super().__init__()
        self.person_url = url_for('person', person_id=mtgo_username) if mtgo_username else None
        self.achievement_descriptions = []
        for a in ach.Achievement.all_achievements:
            desc = {}
            desc['title'] = a.title
            desc['description_safe'] = a.description_safe
            desc['summary'] = a.load_summary()
            self.achievement_descriptions.append(desc)
