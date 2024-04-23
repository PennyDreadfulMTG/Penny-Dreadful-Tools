from decksite.view import View
from magic import rotation, seasons
from shared import dtutil


class Rotation(View):
    def __init__(self, runs: int, num_cards: int) -> None:
        super().__init__()
        self.runs = runs
        self.runs_percent = rotation.runs_percentage(runs)
        self.total_runs = rotation.TOTAL_RUNS
        self.num_cards = num_cards
        if runs > 0:
            self.rotation_msg = 'Rotation is in progress, ends ' + dtutil.display_date(seasons.next_rotation(), 2)
            self.has_cards = True
        else:
            self.rotation_msg = 'Rotation is ' + dtutil.display_date(seasons.next_rotation(), 2)

    def page_title(self) -> str:
        return 'Rotation'
