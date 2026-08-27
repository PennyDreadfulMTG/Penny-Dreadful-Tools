import pytest

from decksite import APP
from decksite.controllers import api


def test_card_api_uses_route_card_parameter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api.oracle, 'load_card', lambda card: {'name': card})

    response = APP.test_client().get('/api/card/Sol%20Ring')

    assert response.status_code == 200
    assert response.get_json() == {'name': 'Sol Ring'}
