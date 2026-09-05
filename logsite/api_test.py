# type: ignore

import pytest

from logsite import APP, api


@pytest.mark.parametrize('path', ['/api/match/2147483647/', '/export/2147483647/'])
def test_missing_match_resources_return_not_found(monkeypatch: pytest.MonkeyPatch, path: str) -> None:
    monkeypatch.setattr(api.match, 'get_match', lambda _match_id: None)

    response = APP.test_client().get(path)
    assert response.status_code == 404


def test_missing_game_resource_returns_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api.game, 'get_game', lambda _game_id: None)

    response = APP.test_client().get('/api/game/2147483647/')
    assert response.status_code == 404


def test_match_exists_returns_false_for_missing_match(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api.match, 'get_match', lambda _match_id: None)

    response = APP.test_client().get('/api/matchExists/2147483647/')

    assert response.status_code == 200
    assert response.get_json() is False
