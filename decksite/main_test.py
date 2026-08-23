import pytest

from decksite import main
from magic.models import Card


def test_image_route_applies_requested_printing_without_mutating_cached_card(monkeypatch: pytest.MonkeyPatch) -> None:
    cached_card = Card({'name': 'Agent Venom'})
    captured = []
    monkeypatch.setattr(main.oracle, 'load_cards', lambda _names: [cached_card])

    def download_image(cards: list[Card]) -> str:
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
