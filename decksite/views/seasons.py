from flask import url_for

from decksite.view import View
from magic import multiverse, rotation


# pylint: disable=no-self-use
class Seasons(View):
    def __init__(self):
        self.seasons = []
        num = 1
        next_rotation_set_code = rotation.next_rotation_ex()['code']
        for code in multiverse.SEASONS:
            if code == next_rotation_set_code:
                break
            self.seasons.append({
                'code': code,
                'num': num,
                'decks_url': url_for('season', season_id=code),
                'league_decks_url': url_for('season', season_id=code, deck_type='league'),
            })
            num += 1

    def subtitle(self):
        return 'Past Seasons'
