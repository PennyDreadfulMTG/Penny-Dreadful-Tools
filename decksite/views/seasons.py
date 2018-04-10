from flask import url_for

from decksite.view import View
from magic import multiverse, rotation


# pylint: disable=no-self-use
class Seasons(View):
    def __init__(self):
        super().__init__()
        self.seasons = self.all_seasons()
        self.seasons.pop() # Don't show "all time" on this page as it is not fully supported yet.

    def subtitle(self):
        return 'Past Seasons'
