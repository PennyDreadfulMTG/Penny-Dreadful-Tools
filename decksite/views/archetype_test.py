import json

from decksite.data.archetype import SeasonStats
from decksite.views.archetype import history_chart


def test_history_chart_includes_win_rate_in_tooltip() -> None:
    season_stats: list[SeasonStats] = [
        {'meta_share': 0.125, 'win_rate': 0.6},
        {'meta_share': 0.0, 'win_rate': None},
    ]

    chart = history_chart(season_stats)
    options = json.loads(chart['options'])

    assert json.loads(chart['series']) == [0.125, 0.0]
    assert options['pd']['tooltip'] == {
        'label': 'Meta Share',
        'additional_label': 'Win Rate',
        'additional_series': [0.6, None],
    }
