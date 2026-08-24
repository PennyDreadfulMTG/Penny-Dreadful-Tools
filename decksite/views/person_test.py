from decksite import APP
from shared_web import template


def test_trailblazer_card_displays_first_played_season() -> None:
    with APP.test_request_context('/'):
        html = template.render_name('person', {
            'has_trailblazer_cards': True,
            'num_trailblazer_cards': 1,
            'trailblazer_cards': [{
                'name': 'Black Lotus',
                'url': '/cards/Black%20Lotus/',
                'first_played_season_icon': '<a href="/seasons/1/"><i class="ss ss-emn ss-common ss-grad"><span class="ss-num">1</span></i></a>',
                'first_played_season_name': 'Season 1',
            }],
        })

    assert 'Cards Played First <span class="card-list-count">· 1</span>' in html
    assert '<a class="card" href="/cards/Black%20Lotus/">Black Lotus</a>' in html
    assert '<span class="trailblazer-season" title="First played in Season 1"><a href="/seasons/1/"><i class="ss ss-emn ss-common ss-grad"><span class="ss-num">1</span></i></a></span>' in html

def test_long_trailblazer_card_list_uses_disclosure_link() -> None:
    with APP.test_request_context('/'):
        html = template.render_name('person', {
            'has_trailblazer_cards': True,
            'has_additional_trailblazer_cards': True,
            'num_trailblazer_cards': 134,
        })

    assert '<a class="trailblazer-card-list-toggle"' in html
    assert '>Show all 134…</a>' in html
    assert '<button class="trailblazer-card-list-toggle"' not in html

def test_seasons_grid_gives_every_season_a_cell() -> None:
    with APP.test_request_context('/'):
        html = template.render_name('person', {
            'seasons_grid_columns': 7,
            'seasons_active': [
                {'season_id': 2, 'className': 'ss-kld season-icon', 'url': '/seasons/2/'},
                {'season_id': 1, 'className': 'ss-emn season-icon inactive', 'url': ''},
            ],
        })

    assert '<p class="season-grid" style="--season-grid-columns: 7">' in html
    assert '<a class="season-icon-link" href="/seasons/2/" title="Season 2"><i class="ss ss-kld season-icon"></i></a>' in html
    assert '<span class="season-icon-link" title="Season 1"><i class="ss ss-emn season-icon inactive"></i></span>' in html
    assert '<br>' not in html
