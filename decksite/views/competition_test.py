import datetime

from decksite.main import APP
from decksite.views.competition import Competition
from magic.models import Competition as CompetitionModel
from shared import dtutil
from shared_web import template


def test_competition_subtitle_shows_season() -> None:
    competition = CompetitionModel({
        'id': 1,
        'name': 'Penny Dreadful Thursdays 14.01',
        'type': 'Gatherling',
        'season_id': 14,
        'start_date': dtutil.GATHERLING_TZ.localize(datetime.datetime(2019, 10, 10, 19)),
        'end_date': dtutil.GATHERLING_TZ.localize(datetime.datetime(2019, 10, 10, 23)),
    })

    with APP.test_request_context('/competitions/1/'):
        view = Competition(competition, [])
        rendered = template.render_name('subtitle', view)

    assert '<a href="/seasons/14/competitions/">Season 14</a>' in rendered
    assert 'Oct 10th, 2019' in rendered
    assert view.season_id() == 14


def test_league_subtitle_shows_exact_date_range() -> None:
    competition = CompetitionModel({
        'id': 2,
        'name': 'League October 2019',
        'type': 'League',
        'season_id': 14,
        'start_date': dtutil.WOTC_TZ.localize(datetime.datetime(2019, 10, 4)),
        'end_date': dtutil.WOTC_TZ.localize(datetime.datetime(2019, 11, 1, 23, 59, 59)),
    })

    with APP.test_request_context('/competitions/2/'):
        rendered = template.render_name('subtitle', Competition(competition, []))

    assert 'Oct 4th, 2019 – Nov 1st, 2019' in rendered
