from unittest.mock import Mock

import pytest
from flask import g

from decksite import main
from magic.models import Card
from shared.pd_exception import TooFewItemsException


def test_image_route_applies_requested_printing_without_mutating_cached_card(monkeypatch: pytest.MonkeyPatch) -> None:
    cached_card = Card({'name': 'Agent Venom'})
    captured = []
    monkeypatch.setattr(main.oracle, 'load_cards', lambda _names: [cached_card])

    def download_image(cards: list[Card], version: str = '') -> str:
        captured.extend(cards)
        return 'LICENSE.md'

    monkeypatch.setattr(main.image_fetcher, 'download_image', download_image)

    with main.APP.test_request_context('/image/Agent%20Venom/?printing=om1&printing_id=d62cf4f8-36a2-4d9f-9d52-53ea18a52760'):
        response = main.image('Agent Venom')

    assert response.status_code == 200
    assert captured[0] is not cached_card
    assert captured[0].preferred_printing == 'om1'
    assert captured[0].preferred_printing_system_id == 'd62cf4f8-36a2-4d9f-9d52-53ea18a52760'
    assert cached_card.get('preferred_printing') is None
    assert cached_card.get('preferred_printing_system_id') is None


def test_image_route_passes_version_through_and_is_cacheable(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}
    monkeypatch.setattr(main.oracle, 'load_cards', lambda _names: [Card({'name': 'Reclaim'})])

    def download_image(cards: list[Card], version: str = '') -> str:
        captured['version'] = version
        return 'LICENSE.md'

    monkeypatch.setattr(main.image_fetcher, 'download_image', download_image)

    with main.APP.test_request_context('/image/Reclaim/?version=art_crop'):
        response = main.image('Reclaim')

    assert response.status_code == 200
    assert captured['version'] == 'art_crop'
    # Without these every card on every page is revalidated against us on every pageview. send_file
    # sets no-cache by default, which silently defeats max_age, so check it is gone.
    assert response.cache_control.public
    assert response.cache_control.max_age == main.IMAGE_MAX_AGE
    assert not response.cache_control.no_cache


def test_image_route_accepts_small_art_crop(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}
    monkeypatch.setattr(main.oracle, 'load_cards', lambda _names: [Card({'name': 'Reclaim'})])

    def download_image(cards: list[Card], version: str = '') -> str:
        captured['version'] = version
        return 'LICENSE.md'

    monkeypatch.setattr(main.image_fetcher, 'download_image', download_image)

    with main.APP.test_request_context('/image/Reclaim/?version=art_crop_small'):
        response = main.image('Reclaim')

    assert response.status_code == 200
    assert captured['version'] == 'art_crop_small'


def test_image_route_rejects_unknown_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main.oracle, 'load_cards', lambda _names: [Card({'name': 'Reclaim'})])

    with main.APP.test_request_context('/image/Reclaim/?version=../../etc/passwd'):
        response = main.image('Reclaim')

    assert response.status_code == 400


def test_image_requests_do_not_touch_the_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """Anything that reads the session adds a Vary: Cookie, which stops Cloudflare caching /image/ at all."""
    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError('/image/ must not read the session')

    monkeypatch.setattr(main.auth, 'check_perms', fail)
    monkeypatch.setattr(main.auth, 'discord_id', fail)
    monkeypatch.setattr(main.auth, 'mtgo_username', fail)

    with main.APP.test_request_context('/image/Reclaim/?version=art_crop'):
        assert main.before_request() is None


@pytest.mark.parametrize('path', ['/seasons/all/decks/', '/seasons/all/decks/league/'])
def test_all_time_deck_requests_are_not_redirected(path: str) -> None:
    with main.APP.test_request_context(path):
        g.season_id = 0

        assert main.before_request() is None


def test_image_teardown_closes_only_the_database_it_used() -> None:
    magic_database = Mock()

    with main.APP.test_request_context('/image/Reclaim/?version=art_crop'):
        g.magic_database = magic_database

    magic_database.close.assert_called_once_with()


def test_image_route_rejects_an_art_crop_of_multiple_cards(monkeypatch: pytest.MonkeyPatch) -> None:
    """/image/a|b/ composites two card images together, which makes no sense for an art crop."""
    monkeypatch.setattr(main.oracle, 'load_cards', lambda names: [Card({'name': n}) for n in names])

    with main.APP.test_request_context('/image/Reclaim|Cremate/?version=art_crop'):
        response = main.image('Reclaim|Cremate')

    assert response.status_code == 400


def test_image_route_fallback_keeps_the_requested_version(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cards we don't have at all still redirect to Scryfall, but should redirect to the right image."""
    def not_found(_names: list[str]) -> list[Card]:
        raise TooFewItemsException('nope')

    monkeypatch.setattr(main.oracle, 'load_cards', not_found)

    with main.APP.test_request_context('/image/Nonesuch/?version=art_crop'):
        response = main.image('Nonesuch')

    assert response.status_code == 303
    assert response.location is not None
    assert response.location == 'https://api.scryfall.com/cards/named?exact=Nonesuch&format=image&version=art_crop'


def test_small_art_crop_fallback_uses_scryfalls_art_crop(monkeypatch: pytest.MonkeyPatch) -> None:
    def not_found(_names: list[str]) -> list[Card]:
        raise TooFewItemsException('nope')

    monkeypatch.setattr(main.oracle, 'load_cards', not_found)

    with main.APP.test_request_context('/image/Nonesuch/?version=art_crop_small'):
        response = main.image('Nonesuch')

    assert response.status_code == 303
    assert response.location == 'https://api.scryfall.com/cards/named?exact=Nonesuch&format=image&version=art_crop'


def test_image_route_returns_404_when_the_fetch_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main.oracle, 'load_cards', lambda _names: [Card({'name': 'Lovestruck Beast'})])
    monkeypatch.setattr(main.image_fetcher, 'download_image', lambda cards, version='': None)

    with main.APP.test_request_context('/image/Lovestruck%20Beast/?version=art_crop'):
        response = main.image('Lovestruck Beast')

    assert response.status_code == 404


def test_unknown_card_fallback_encodes_user_input(monkeypatch: pytest.MonkeyPatch) -> None:
    def not_found(_names: list[str]) -> list[Card]:
        raise TooFewItemsException('nope')

    monkeypatch.setattr(main.oracle, 'load_cards', not_found)

    with main.APP.test_request_context('/image/Name%26format%3Djson/?version=art_crop'):
        response = main.image('Name&format=json')

    assert response.status_code == 303
    assert response.location == 'https://api.scryfall.com/cards/named?exact=Name%26format%3Djson&format=image&version=art_crop'
