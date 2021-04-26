import datetime

from decksite.view import View
from magic import rotation, seasons
from shared import configuration, dtutil


# pylint: disable=no-self-use,too-many-instance-attributes
class Rotation(View):
    def __init__(self) -> None:
        super().__init__()
        until_rotation = seasons.next_rotation() - dtutil.now()
        in_rotation = configuration.get_bool('always_show_rotation')
        if until_rotation < datetime.timedelta(7):
            in_rotation = True
            self.rotation_msg = 'Rotation is in progress, ends ' + dtutil.display_date(seasons.next_rotation(), 2)
        else:
            self.rotation_msg = 'Rotation is ' + dtutil.display_date(seasons.next_rotation(), 2)
        if in_rotation:
            self.in_rotation = in_rotation
            self.runs, self.runs_percent, self.cards = rotation.read_rotation_files()
        else:
            self.cards = []
        self.num_cards = len(self.cards)

    def page_title(self) -> str:
        return 'Rotation'
