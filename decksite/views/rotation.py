import datetime
from typing import Optional, Union

from flask import session

from decksite.data import card
from decksite.view import View
from magic import rotation
from magic.models import Card
from shared import configuration, dtutil


# pylint: disable=no-self-use,too-many-instance-attributes
class Rotation(View):
    def __init__(self, interestingness: Optional[str] = None, query: Optional[str] = '') -> None:
        super().__init__()
        until_rotation = rotation.next_rotation() - dtutil.now()
        in_rotation = configuration.get_bool('always_show_rotation')
        if until_rotation < datetime.timedelta(7):
            in_rotation = True
            self.rotation_msg = 'Totation is in progress, ends ' + dtutil.display_date(rotation.next_rotation(), 2)
        else:
            self.rotation_msg = 'Rotation is ' + dtutil.display_date(rotation.next_rotation(), 2)
        if in_rotation:
            self.in_rotation = in_rotation
            self.show_interestingness_filter = True
            self.runs, self.runs_percent, self.cards = rotation.read_rotation_files()
            # Now add interestingness to the cards, which only decksite knows not magic.rotation.
            playability = card.playability()
            c: Card
            for c in self.cards:
                c.interestingness = rotation.interesting(playability, c)
        else:
            self.cards = []
        self.show_interesting = True
        if interestingness:
            self.cards = [c for c in self.cards if c.get('interestingness') == interestingness]
        self.num_cards = len(self.cards)
        self.query = query
        self.show_filters_toggle = True
        if session.get('admin'):
            return
        self.cards = [c for c in self.cards if c.status != 'Legal']
        for c in self.cards:
            if c.status != 'Undecided':
                continue
            c.hits = redact(c.hits)
            c.hits_needed = redact(c.hits_needed)
            c.percent = redact(c.percent)
            c.percent_needed = redact(c.percent_needed)

    def page_title(self) -> str:
        return 'Rotation'

def redact(num: Union[str, int, float]) -> str:
    return ''.join(['█' for _ in str(num)])
