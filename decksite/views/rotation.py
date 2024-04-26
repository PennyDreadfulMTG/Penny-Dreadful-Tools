from decksite.view import View
from magic import rotation, seasons
from shared import dtutil


class Rotation(View):
    def __init__(self, in_rotation: bool, runs: int, num_cards: int) -> None:
        super().__init__()
        self.runs = runs
        self.runs_percent = rotation.runs_percentage(runs)
        self.total_runs = rotation.TOTAL_RUNS
        self.num_cards = num_cards
        self.has_cards = runs > 0
        prefix = 'Rotation is in progress, ends ' if in_rotation else 'Rotation is '
        display_date = dtutil.display_date(seasons.next_rotation(), 2)
        self.rotation_msg = prefix + display_date
        self.note = 'Data from the last rotation is shown' if runs and not in_rotation else ''

    def page_title(self) -> str:
        return 'Rotation'
