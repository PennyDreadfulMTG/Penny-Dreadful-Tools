import datetime
from typing import Any, cast

from decksite.view import View
from magic import oracle
from shared import dtutil


class Seasons(View):
    def __init__(self, stats: dict[int, dict[str, int | datetime.datetime]]) -> None:
        super().__init__()
        seasons = self.all_seasons()
        seasons.pop()  # Don't show "all time" on this page as it is not fully supported yet.
        cards_count: dict[str, int] = {}
        for c in oracle.CARDS_BY_NAME.values():
            for f, is_legal in c.legalities.items():
                if is_legal and 'Penny Dreadful' in f:
                    cards_count[f] = cards_count.get(f, 0) + 1
        self.seasons: list[dict[str, Any]] = []
        for season_info in seasons:
            season: dict[str, Any] = {}
            season.update(season_info)
            season_stats = stats.get(cast(int, season['num']), {})
            season.update(season_stats)
            if season.get('start_date') is None:
                continue
            season['matches_per_day'] = round(season['num_matches'] / season['length_in_days'])
            season['decks_per_day'] = round(season['num_decks'] / season['length_in_days'])
            season['num_legal_cards'] = cards_count.get(str(season_info['legality_name']), 0)
            for k, v in season.items():
                if isinstance(v, int):
                    season[k] = f'{v:,}'  # Human-friendly number formatting like "29,000".
            season['start_date_display'] = dtutil.display_date(season['start_date'])
            season['length_in_days'] = season['length_in_days'] + ' days'
            if season.get('end_date'):
                season['end_date_display'] = dtutil.display_date(season['end_date'])
            else:
                season['end_date_display'] = 'Now'
                season['length_in_days'] += ' so far'
            self.seasons.append(season)

    def page_title(self) -> str:
        return 'Past Seasons'
