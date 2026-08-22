from typing import Any, cast

import pytest
from flask import g

from decksite.controllers import metagame
from decksite.main import APP


@pytest.mark.parametrize(
    ('path', 'deck_type', 'expected'),
    [
        ('/cards/A%20Most%20Helpful%20Weaver/', None, '/cards/Origin%20of%20Spider-Man/'),
        ('/cards/A%20Most%20Helpful%20Weaver/tournament/', 'tournament', '/cards/Origin%20of%20Spider-Man/tournament/'),
    ],
)
def test_alias_card_pages_redirect_to_the_canonical_url(
    path: str,
    deck_type: str | None,
    expected: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        metagame.oracle,
        'valid_name',
        lambda name: 'Origin of Spider-Man' if name == 'A Most Helpful Weaver' else name,
    )
    monkeypatch.setattr(metagame.cs, 'load_card', lambda *_args, **_kwargs: pytest.fail('Redirects must not load the card page'))

    with APP.test_request_context(path):
        response = cast(Any, metagame.card).__wrapped__(name='A Most Helpful Weaver', deck_type=deck_type)

    assert response.status_code == 302
    assert response.location == expected


def test_canonical_card_pages_do_not_redirect(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(metagame.oracle, 'valid_name', lambda name: name)
    monkeypatch.setattr(metagame.cs, 'load_card', lambda *_args, **_kwargs: object())

    class FakeCardView:
        def __init__(self, _card: object, _tournament_only: bool) -> None:
            pass

        def page(self) -> str:
            return 'canonical card page'

    monkeypatch.setattr(metagame, 'Card', FakeCardView)
    with APP.test_request_context('/cards/Origin%20of%20Spider-Man/'):
        response = cast(Any, metagame.card).__wrapped__(name='Origin of Spider-Man')

    assert response == 'canonical card page'


def test_alias_card_page_redirect_preserves_the_season(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        metagame.oracle,
        'valid_name',
        lambda name: 'Origin of Spider-Man' if name == 'A Most Helpful Weaver' else name,
    )
    with APP.test_request_context('/seasons/5/cards/A%20Most%20Helpful%20Weaver/tournament/'):
        g.season_id = 5
        response = cast(Any, metagame.card).__wrapped__(name='A Most Helpful Weaver', deck_type='tournament')

    assert response.status_code == 302
    assert response.location == '/seasons/5/cards/Origin%20of%20Spider-Man/tournament/'
