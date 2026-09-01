from typing import Any, cast

import pytest
from flask import g

from decksite.controllers import metagame
from decksite.main import APP
from magic.models import Card


@pytest.mark.parametrize(
    ('path', 'deck_type', 'expected'),
    [
        ('/cards/Origin%20of%20Spiderman/', None, '/cards/Origin%20of%20Spider-Man/'),
        ('/cards/Origin%20of%20Spiderman/tournament/', 'tournament', '/cards/Origin%20of%20Spider-Man/tournament/'),
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
        lambda name: 'Origin of Spider-Man' if name == 'Origin of Spiderman' else name,
    )
    monkeypatch.setattr(metagame.cs, 'load_card', lambda *_args, **_kwargs: Card({'name': 'Origin of Spider-Man'}))

    with APP.test_request_context(path):
        response = cast(Any, metagame.card).__wrapped__(name='Origin of Spiderman', deck_type=deck_type)

    assert response.status_code == 302
    assert response.location == expected


def test_official_alternate_name_renders_the_card_page_without_redirect(monkeypatch: pytest.MonkeyPatch) -> None:
    card = Card({'name': 'Origin of Spider-Man', 'flavor_names': 'A Most Helpful Weaver'})
    monkeypatch.setattr(
        metagame.oracle,
        'valid_name',
        lambda name: 'Origin of Spider-Man' if name == 'A Most Helpful Weaver' else name,
    )
    monkeypatch.setattr(metagame.cs, 'load_card', lambda *_args, **_kwargs: card)
    monkeypatch.setattr(metagame.cs, 'load_card_person_stats', lambda *_args, **_kwargs: ([], []))

    class FakeCardView:
        def __init__(self, loaded_card: Card, _tournament_only: bool, alternate_name: str | None, *_args: object, **_kwargs: object) -> None:
            assert loaded_card is card
            assert alternate_name == 'A Most Helpful Weaver'

        def page(self) -> str:
            return 'alternate card page'

    monkeypatch.setattr(metagame, 'Card', FakeCardView)
    with APP.test_request_context('/cards/A%20Most%20Helpful%20Weaver/'):
        response = cast(Any, metagame.card).__wrapped__(name='A Most Helpful Weaver')

    assert response == 'alternate card page'


def test_canonical_card_pages_do_not_redirect(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(metagame.oracle, 'valid_name', lambda name: name)
    monkeypatch.setattr(metagame.cs, 'load_card', lambda *_args, **_kwargs: Card({'name': 'Origin of Spider-Man'}))
    monkeypatch.setattr(metagame.cs, 'load_card_person_stats', lambda *_args, **_kwargs: ([], []))

    class FakeCardView:
        def __init__(self, _card: object, _tournament_only: bool, alternate_name: str | None, *_args: object, **_kwargs: object) -> None:
            assert alternate_name is None

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
        lambda name: 'Origin of Spider-Man' if name == 'Origin of Spiderman' else name,
    )
    monkeypatch.setattr(metagame.cs, 'load_card', lambda *_args, **_kwargs: Card({'name': 'Origin of Spider-Man'}))
    with APP.test_request_context('/seasons/5/cards/Origin%20of%20Spiderman/tournament/'):
        g.season_id = 5
        response = cast(Any, metagame.card).__wrapped__(name='Origin of Spiderman', deck_type='tournament')

    assert response.status_code == 302
    assert response.location == '/seasons/5/cards/Origin%20of%20Spider-Man/tournament/'


def test_split_cards_do_not_redirect_when_the_proxy_has_merged_the_slashes(monkeypatch: pytest.MonkeyPatch) -> None:
    # The proxies in front of us merge `//` into `/`, so redirecting to the canonical spelling loops forever.
    monkeypatch.setattr(
        metagame.oracle,
        'valid_name',
        lambda name: 'Bedeck // Bedazzle' if name in ('Bedeck / Bedazzle', 'Bedeck // Bedazzle') else name,
    )
    monkeypatch.setattr(metagame.cs, 'load_card', lambda *_args, **_kwargs: Card({'name': 'Bedeck // Bedazzle'}))
    monkeypatch.setattr(metagame.cs, 'load_card_person_stats', lambda *_args, **_kwargs: ([], []))

    class FakeCardView:
        def __init__(self, _card: object, _tournament_only: bool, alternate_name: str | None, *_args: object, **_kwargs: object) -> None:
            assert alternate_name is None

        def page(self) -> str:
            return 'split card page'

    monkeypatch.setattr(metagame, 'Card', FakeCardView)
    with APP.test_request_context('/cards/Bedeck%20/%20Bedazzle/'):
        response = cast(Any, metagame.card).__wrapped__(name='Bedeck / Bedazzle')

    assert response == 'split card page'


@pytest.mark.parametrize(
    ('submitted', 'canonical', 'expected'),
    [
        ('Bedeck / Bedazzle', 'Bedeck // Bedazzle', True),
        ('Bedeck // Bedazzle', 'Bedeck // Bedazzle', True),
        ('Bedeck//Bedazzle', 'Bedeck // Bedazzle', True),
        ('Origin of Spiderman', 'Origin of Spider-Man', False),
        ('Fire / Ice', 'Bedeck // Bedazzle', False),
    ],
)
def test_is_canonical_url_name(submitted: str, canonical: str, expected: bool) -> None:
    assert metagame.is_canonical_url_name(submitted, canonical) == expected
