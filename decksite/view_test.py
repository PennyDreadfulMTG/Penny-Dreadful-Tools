from decksite import view
from decksite.main import APP
from magic import seasons


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
