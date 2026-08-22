from typing import Any, cast

import pytest

from decksite.controllers import admin
from decksite.data import deck
from decksite.main import APP
from decksite.views import EditArchetypes, EditRules
from shared.pd_exception import InvalidDataException


def test_post_archetypes_reports_invalid_card_names(monkeypatch: pytest.MonkeyPatch) -> None:
    def valid_name(name: str) -> str:
        if name in ['Not a Card', 'Also Not a Card']:
            raise InvalidDataException()
        return name

    def load_decks_by_cards(names: list[str], not_names: list[str]) -> None:
        pytest.fail(f'Should not search for decks with invalid card names: {names}, {not_names}')

    def edit_archetypes(q: str = '', notq: str = '', query_errors: list[str] | None = None, notquery_errors: list[str] | None = None) -> str:
        return EditArchetypes([], q, notq, query_errors, notquery_errors).render_content()

    monkeypatch.setattr(admin.oracle, 'valid_name', valid_name)
    monkeypatch.setattr(admin.ds, 'load_decks_by_cards', load_decks_by_cards)
    monkeypatch.setattr(admin, 'edit_archetypes', edit_archetypes)
    monkeypatch.setattr(deck, 'load_decks', lambda *args, **kwargs: ([], 0))
    monkeypatch.setattr(deck, 'load_queue_similarity', lambda decks: None)
    with APP.test_request_context('/admin/archetypes/', method='POST', data={'q': 'Dark Ritual\nNot a Card', 'notq': 'Also Not a Card'}):
        response = cast(Any, admin.post_archetypes).__wrapped__()
    assert 'Card not found: Not a Card' in response
    assert 'Card not found: Also Not a Card' in response
    assert '<textarea name="q" id="q" class="error" aria-invalid="true" aria-describedby="q-error">Dark Ritual\nNot a Card</textarea>' in response
    assert '<textarea name="notq" id="notq" class="error" aria-invalid="true" aria-describedby="notq-error">Also Not a Card</textarea>' in response


def test_validate_card_names_canonicalizes_and_ignores_blank_lines(monkeypatch: pytest.MonkeyPatch) -> None:
    def valid_name(name: str) -> str:
        if name == 'Not a Card':
            raise InvalidDataException()
        return name.title()

    monkeypatch.setattr(admin.oracle, 'valid_name', valid_name)
    names, errors = admin.validate_card_names(' dark ritual \n\nSWAMP\nNot a Card')
    assert names == ['Dark Ritual', 'Swamp']
    assert errors == ['Card not found: Not a Card']


def test_post_rules_requires_archetype(monkeypatch: pytest.MonkeyPatch) -> None:
    def edit_rules(errors: list[str] | None = None) -> str:
        return EditRules(0, 0, [], [], [], [], [], [], errors).render_content()

    monkeypatch.setattr(admin, 'edit_rules', edit_rules)
    with APP.test_request_context('/admin/rules/', method='POST', data={'archetype_id': '', 'include': '4 Lightning Bolt'}):
        response = cast(Any, admin.post_rules).__wrapped__()
    assert 'Please select an archetype.' in response
    assert '<select name="archetype_id" required class="error" aria-describedby="archetype-error">' in response
