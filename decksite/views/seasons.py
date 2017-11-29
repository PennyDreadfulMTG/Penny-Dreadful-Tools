from flask import url_for

from magic import multiverse

from decksite.view import View

# pylint: disable=no-self-use
class Seasons(View):
    def __init__(self):
        self.seasons = []
        num = 1
        for code in multiverse.SEASONS:
            self.seasons.append({
                'code': code,
                'num': num,
                'url': url_for('season', season_id=code),
            })
            num += 1

    def subtitle(self):
        return 'Past Seasons'
