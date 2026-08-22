from decksite import view
from decksite.main import APP
from magic import seasons
from shared_web import template


def test_seasonized_url_for_app() -> None:
    with APP.test_request_context('/decks/'):
        assert view.seasonized_url(1) == '/seasons/1/decks/'
        assert view.seasonized_url(seasons.current_season_num()) == '/decks/'

def test_seasonized_url_for_seasons() -> None:
    with APP.test_request_context('/seasons/2/decks/'):
        assert view.seasonized_url(1) == '/seasons/1/decks/'
        assert view.seasonized_url(seasons.current_season_num()) == '/decks/'

def test_seasonized_url_simple() -> None:
    with APP.test_request_context('/tournaments/'):
        assert view.seasonized_url(1) == '/tournaments/'
        assert view.seasonized_url(seasons.current_season_num()) == '/tournaments/'

def test_intro_deck_links() -> None:
    with APP.test_request_context('/'):
        v = view.View()
        rendered = template.render_name('faqsbody', v)
        assert 'href="/metagame/"' in rendered
