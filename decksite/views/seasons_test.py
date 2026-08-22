import datetime

import pytest

from decksite.main import APP
from decksite.view import View
from decksite.views.seasons import Seasons
from magic import oracle


def test_includes_season_one_but_not_all_time(monkeypatch: pytest.MonkeyPatch) -> None:
    all_seasons = [
        {'name': 'All Time', 'num': None},
        {'name': 'Season 2', 'num': 2, 'legality_name': 'Penny Dreadful KLD'},
        {'name': 'Season 1', 'num': 1, 'legality_name': 'Penny Dreadful EMN'},
    ]
    stats: dict[int, dict[str, int | datetime.datetime]] = {
        season_id: {
            'start_date': datetime.datetime(2016, season_id, 1, tzinfo=datetime.UTC),
            'end_date': datetime.datetime(2016, season_id + 1, 1, tzinfo=datetime.UTC),
            'length_in_days': 30,
            'num_decks': 1,
            'num_matches': 1,
        }
        for season_id in [1, 2]
    }
    monkeypatch.setattr(View, 'all_seasons', lambda self: all_seasons)
    monkeypatch.setattr(oracle, 'CARDS_BY_NAME', {})

    with APP.test_request_context('/seasons/'):
        view = Seasons(stats)

    assert [season['num'] for season in view.seasons] == ['2', '1']
