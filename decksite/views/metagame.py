import math

from flask import url_for

from decksite.data.archetype import Archetype
from decksite.deck_type import DeckType
from decksite.view import View
from magic import image_fetcher, oracle

LEFT_PADDING = 2
TOTAL_HEIGHT = 20000


class Metagame(View):
    def __init__(self, archetypes: list[Archetype], tournament_only: bool, key_cards: dict[int, str]) -> None:
        super().__init__()

        self.decks = []
        self.show_seasons = True
        self.tournament_only = self.hide_perfect_runs = tournament_only
        self.show_tournament_toggle = True
        self.toggle_results_url = url_for('.metagame', deck_type=None if tournament_only else DeckType.TOURNAMENT.value)

        # We say '' for "no win percent" not a number or None, which can cause this page to error if we try to do math on ''. Let's just skip those instead.
        archetypes = [a for a in archetypes if a.win_percent != '']
        self.archetypes = []
        total_matches_log = sum([math.log2((a.wins or 0) + (a.losses or 0) + (a.draws or 0) + 1) for a in archetypes])
        height = min(TOTAL_HEIGHT, len(archetypes) * 200)
        for a in archetypes:
            card = key_cards.get(a.id)
            a.num_matches = (a.wins or 0) + (a.losses or 0) + (a.draws or 0)
            if a.num_matches > 0:
                a.display_width = max(float(a.win_percent) - LEFT_PADDING if a.win_percent else 0, 0)
                a.display_height = math.log2(a.num_matches + 1) / total_matches_log * height
                a.font_size = min(a.display_height / 2, 20)
                if card:
                    url = image_fetcher.scryfall_image(oracle.load_card(card), 'art_crop')
                    a.background = f'linear-gradient(0deg, rgba(0,0,0,0.2), rgba(0,0,0,0.2)), url({url}) center top / cover no-repeat'
                else:
                    a.background = '#ccc'
                a.num_matches_plural = 'es' if a.num_matches != 1 else ''
                a.lower_bound, a.upper_bound = confidence_interval(float(a.win_percent) / 100.0, a.num_matches)
                a.lower_win_percent = round(a.lower_bound * 100.0, 1)
                a.upper_win_percent = round(a.upper_bound * 100.0, 1)
                self.archetypes.append(a)
        self.archetypes.sort(key=lambda o: (o.lower_bound, o.display_width, o.num_matches), reverse=True)

    def page_title(self) -> str:
        return 'Metagame'

# Calculation the lower and upper bound using the Wilson interval at 95% confidence.
# See https://discord.com/channels/207281932214599682/230056266938974218/691464882998214686
# See https://stackoverflow.com/a/10029645/375262
# See https://www.evanmiller.org/how-not-to-sort-by-average-rating.html
# Expects win_rate as a fraction of 1 NOT a 0-100 scale percentage.
def confidence_interval(win_rate: float, matches_played: int) -> tuple[float, float]:
    if matches_played == 0:
        return 0.0, 0.0
    n = float(matches_played)
    z = 1.96  # 1.44 = 85%, 1.96 = 95%, see https://www.dummies.com/education/math/statistics/checking-out-statistical-confidence-interval-critical-values/
    phat = win_rate
    lower_bound = (phat + z * z / (2 * n) - z * math.sqrt((phat * (1 - phat) + z * z / (4 * n)) / n)) / (1 + z * z / n)
    upper_bound = (phat + z * z / (2 * n) + z * math.sqrt((phat * (1 - phat) + z * z / (4 * n)) / n)) / (1 + z * z / n)
    return lower_bound, upper_bound
