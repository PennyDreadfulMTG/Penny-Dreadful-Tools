import datetime
from typing import Optional

from flask import session

from decksite.data import card
from decksite.view import View
from magic import rotation, rotation_info
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
            self.rotation_msg = 'Rotation is in progress, ends ' + dtutil.display_date(rotation.next_rotation(), 2)
        else:
            self.rotation_msg = 'Rotation is ' + dtutil.display_date(rotation.next_rotation(), 2)
        if in_rotation:
            self.in_rotation = in_rotation
            self.show_interestingness_filter = True
            self.runs, self.runs_percent, self.cards = rotation_info.read_rotation_files()
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
        self.cards = [c for c in self.cards if visible(c)]

    def page_title(self) -> str:
        return 'Rotation'


def visible(c: Card) -> bool:
    return c.status != 'Undecided' or session.get('admin')
