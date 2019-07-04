import datetime
from typing import Optional

from decksite.data import card
from decksite.view import View
from magic import rotation
from magic.models import Card
from shared import configuration, dtutil


# pylint: disable=no-self-use,too-many-instance-attributes
class Rotation(View):
    def __init__(self, interestingness: Optional[str] = None, query: Optional[str] = '') -> None:
        super().__init__()
        until_full_rotation = rotation.next_rotation() - dtutil.now()
        until_supplemental_rotation = rotation.next_supplemental() - dtutil.now()
        in_rotation = configuration.get_bool('always_show_rotation')
        if until_full_rotation < datetime.timedelta(7):
            in_rotation = True
            self.rotation_msg = 'Full rotation is in progress, ends ' + dtutil.display_date(rotation.next_rotation(), 2)
        elif until_supplemental_rotation < datetime.timedelta(7):
            in_rotation = True
            self.rotation_msg = 'Supplemental rotation is in progress, ends ' + dtutil.display_date(rotation.next_supplemental(), 2)
        elif until_full_rotation < until_supplemental_rotation:
            self.rotation_msg = 'Full rotation is ' + dtutil.display_date(rotation.next_rotation(), 2)
        else:
            self.rotation_msg = 'Supplemental rotation is ' + dtutil.display_date(rotation.next_supplemental(), 2)
        if in_rotation:
            self.in_rotation = in_rotation
            self.runs, self.runs_percent, self.cards = rotation.read_rotation_files()
            # Now add interestingness to the cards, which only decksite knows not magic.rotation.
            playability = card.playability()
            c: Card
            for c in self.cards:
                c.interestingness = rotation.interesting(playability, c)
        self.show_interesting = True
        if interestingness:
            self.cards = [c for c in self.cards if c.get('interestingness') == interestingness]
        self.num_cards = len(self.cards)
        self.query = query

    def page_title(self) -> str:
        return 'Rotation'
