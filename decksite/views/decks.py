from flask import url_for
from flask_babel import ngettext

from decksite.view import View
from magic import rotation


# pylint: disable=no-self-use
class Decks(View):
    def __init__(self, decks):
        active_runs = [d for d in decks if d.is_in_current_run()]
        self.active_runs = ngettext('%(num)d active league run', '%(num)d active league runs', len(active_runs))
        self.decks = [d for d in decks if d not in active_runs]
        self.season_url = url_for('season', season_id=rotation.last_rotation_ex()['code'])

    def subtitle(self):
        return 'Latest Decks'
