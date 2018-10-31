from flask import url_for

import decksite.achievements as ach
from decksite import get_season_id
from decksite.data import person
from decksite.view import View
from shared.container import Container


# pylint: disable=no-self-use
class Achievements(View):
    def __init__(self, mtgo_username):
        super().__init__()
        self.person_url = url_for('person', person_id=mtgo_username) if mtgo_username else None
        self.achievement_descriptions = []
        for a in ach.Achievement.all_achievements:
            desc = Container({'title': a.title, 'description_safe': a.description_safe})
            desc.summary = a.load_summary(season_id=get_season_id())
            if mtgo_username:
                p = person.load_person_by_mtgo_username(mtgo_username, season_id=get_season_id())
                desc.detail = a.display(p)
            else:
                desc.detail = ''
            desc.percent = a.percent(season_id=get_season_id())
            lb = a.leaderboard(season_id=get_season_id())
            if lb is not None:
                desc.leaderboard = lb
                pos = 1
                for ix, entry in enumerate(lb):
                    if ix > 0 and entry['points'] < last_entry['points']:
                        pos = ix + 1
                    entry['pos'] = pos
                    entry['position'] = chr(9311 + pos)
                    last_entry = entry
                desc['has_leaderboard'] = True
                desc['leaderboard_heading'] = a.leaderboard_heading()
            self.achievement_descriptions.append(desc)
        self.show_seasons = True
    @staticmethod
    def page_title():
        return 'Achievements'
