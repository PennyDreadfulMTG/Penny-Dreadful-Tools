from unittest.mock import Mock, patch

from decksite import view
from decksite.main import APP
from decksite.views.person_achievements import PersonAchievements
from magic import seasons
from shared.container import Container
from shared_web import template
from shared_web.base_view import BaseView


def test_person_achievements_prepare_active_runs() -> None:
    active_decks = [Mock(), Mock()]
    for deck in active_decks:
        deck.is_in_current_run.return_value = True
    completed_deck = Mock()
    completed_deck.is_in_current_run.return_value = False
    detail = Container({'decks': active_decks + [completed_deck]})
    achievement = Container({'detail': detail, 'legend': 'Achievement earned'})
    person = Container({'name': 'Achievement Hunter'})

    with APP.test_request_context('/'):
        achievement_view = PersonAchievements(person, [achievement], [])
        achievement_view.prepare_decks()

    assert detail.active_runs_text == '2 active league runs'
    assert detail.decks == [completed_deck]


def test_seasonized_url_for_app() -> None:
    with APP.test_request_context('/decks/'):
        assert view.seasonized_url(1) == '/seasons/1/decks/'
        assert view.seasonized_url(seasons.current_season_num()) == '/decks/'


def test_font_url_cache_busts_regenerated_font() -> None:
    with APP.test_request_context('/'), patch('shared_web.base_view.os.path.getmtime', return_value=123):
        assert BaseView().font_url() == '/static/fonts/symbols.woff2?v=123'

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
