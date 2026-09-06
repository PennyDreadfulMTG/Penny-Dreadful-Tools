from typing import Any, cast

import pytest

from decksite.controllers import admin
from decksite.data import deck
from decksite.league import EditMatchForm
from decksite.main import APP
from decksite.views import EditArchetypes, EditMatches, EditRules
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
    monkeypatch.setattr(deck, 'load_decks', lambda *args, **kwargs: [])
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


def test_post_archetypes_creates_rule_with_new_archetype(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[Any, ...]] = []

    def add_archetype(name: str, parent: int, description: str) -> int:
        calls.append(('archetype', name, parent, description))
        return 42

    def add_rule(archetype_id: int) -> int:
        calls.append(('rule', archetype_id))
        return 99

    def parse_cards_raw(include: str, exclude: str) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
        calls.append(('parse', include, exclude))
        return [(4, 'Delver of Secrets')], [(1, 'Tolarian Terror')]

    def update_cards(rule_id: int, include: list[tuple[int, str]], exclude: list[tuple[int, str]]) -> None:
        calls.append(('cards', rule_id, include, exclude))

    monkeypatch.setattr(admin.archs, 'add', add_archetype)
    monkeypatch.setattr(admin.archs, 'archetype_exists', lambda archetype_id: True)
    monkeypatch.setattr(admin.archs, 'name_exists', lambda name: False)
    monkeypatch.setattr(admin.rs, 'add_rule', add_rule)
    monkeypatch.setattr(admin.rs, 'parse_cards_raw', parse_cards_raw)
    monkeypatch.setattr(admin.rs, 'update_cards', update_cards)
    monkeypatch.setattr(admin, 'edit_archetypes', lambda *args: 'done')

    data = {
        'parent': '7',
        'name': 'Tempo Spells',
        'description': 'Cheap threats backed by interaction.',
        'include': '4 Delver of Secrets',
        'exclude': '1 Tolarian Terror',
    }
    with APP.test_request_context('/admin/archetypes/', method='POST', data=data):
        response = cast(Any, admin.post_archetypes).__wrapped__()

    assert response == 'done'
    assert calls == [
        ('parse', '4 Delver of Secrets', '1 Tolarian Terror'),
        ('archetype', 'Tempo Spells', 7, 'Cheap threats backed by interaction.'),
        ('rule', 42),
        ('cards', 99, [(4, 'Delver of Secrets')], [(1, 'Tolarian Terror')]),
    ]


def test_post_archetypes_does_not_create_empty_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(admin.rs, 'parse_cards_raw', lambda include, exclude: ([], []))
    monkeypatch.setattr(admin.archs, 'archetype_exists', lambda archetype_id: True)
    monkeypatch.setattr(admin.archs, 'name_exists', lambda name: False)
    monkeypatch.setattr(admin.archs, 'add', lambda name, parent, description: 42)
    monkeypatch.setattr(admin.rs, 'add_rule', lambda archetype_id: pytest.fail('Should not create an empty rule'))
    monkeypatch.setattr(admin, 'edit_archetypes', lambda *args: 'done')

    with APP.test_request_context('/admin/archetypes/', method='POST', data={'parent': '7', 'name': 'Tempo Spells', 'description': 'Description'}):
        response = cast(Any, admin.post_archetypes).__wrapped__()

    assert response == 'done'


def test_post_archetypes_validates_rule_before_creating_archetype(monkeypatch: pytest.MonkeyPatch) -> None:
    def parse_cards_raw(include: str, exclude: str) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
        raise InvalidDataException('Card not found in any deck: 4 Not a Card')

    def edit_archetypes(q: str = '', notq: str = '', query_errors: list[str] | None = None, notquery_errors: list[str] | None = None, add_errors: list[str] | None = None, add_values: dict[str, str] | None = None) -> str:
        return EditArchetypes([], q, notq, query_errors, notquery_errors, add_errors, add_values).render_content()

    monkeypatch.setattr(admin.rs, 'parse_cards_raw', parse_cards_raw)
    monkeypatch.setattr(admin.archs, 'archetype_exists', lambda archetype_id: True)
    monkeypatch.setattr(admin.archs, 'name_exists', lambda name: False)
    monkeypatch.setattr(admin.archs, 'add', lambda *args: pytest.fail('Should not create an archetype with an invalid rule'))
    monkeypatch.setattr(admin.rs, 'add_rule', lambda archetype_id: pytest.fail('Should not create an invalid rule'))
    monkeypatch.setattr(admin, 'edit_archetypes', edit_archetypes)
    monkeypatch.setattr(deck, 'load_decks', lambda *args, **kwargs: [])
    monkeypatch.setattr(deck, 'load_queue_similarity', lambda decks: None)
    data = {
        'parent': '7',
        'name': 'Tempo Spells',
        'description': 'Cheap threats backed by interaction.',
        'include': '4 Not a Card',
        'exclude': '1 Tolarian Terror',
    }

    with APP.test_request_context('/admin/archetypes/', method='POST', data=data):
        response = cast(Any, admin.post_archetypes).__wrapped__()

    assert 'Card not found in any deck: 4 Not a Card' in response
    assert 'value="Tempo Spells"' in response
    assert 'value="Cheap threats backed by interaction."' in response
    assert '>4 Not a Card</textarea>' in response
    assert '>1 Tolarian Terror</textarea>' in response


@pytest.mark.parametrize('parent', ['', 'not-an-id', '999999'])
def test_post_archetypes_reports_invalid_parent_without_writing(monkeypatch: pytest.MonkeyPatch, parent: str) -> None:
    def edit_archetypes(q: str = '', notq: str = '', query_errors: list[str] | None = None, notquery_errors: list[str] | None = None, add_errors: list[str] | None = None, add_values: dict[str, str] | None = None) -> str:
        assert add_values is not None
        assert add_values.get('name') == 'Tempo Spells'
        return '\n'.join(add_errors or [])

    monkeypatch.setattr(admin.archs, 'archetype_exists', lambda archetype_id: False)
    monkeypatch.setattr(admin.archs, 'name_exists', lambda name: False)
    monkeypatch.setattr(admin.archs, 'add', lambda *args: pytest.fail('Should not create an archetype with an invalid parent'))
    monkeypatch.setattr(admin.rs, 'parse_cards_raw', lambda include, exclude: ([], []))
    monkeypatch.setattr(admin, 'edit_archetypes', edit_archetypes)

    with APP.test_request_context('/admin/archetypes/', method='POST', data={'create_archetype': '1', 'parent': parent, 'name': 'Tempo Spells'}):
        response = cast(Any, admin.post_archetypes).__wrapped__()

    assert response == 'Please select a valid parent archetype.'


def test_post_archetypes_reports_blank_name_without_writing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(admin.archs, 'archetype_exists', lambda archetype_id: True)
    monkeypatch.setattr(admin.archs, 'name_exists', lambda name: pytest.fail('Should not check a blank name'))
    monkeypatch.setattr(admin.archs, 'add', lambda *args: pytest.fail('Should not create an unnamed archetype'))
    monkeypatch.setattr(admin.rs, 'parse_cards_raw', lambda include, exclude: ([], []))
    monkeypatch.setattr(admin, 'edit_archetypes', lambda *args, **kwargs: '\n'.join(kwargs.get('add_errors') or []))

    with APP.test_request_context('/admin/archetypes/', method='POST', data={'create_archetype': '1', 'parent': '7', 'name': '   '}):
        response = cast(Any, admin.post_archetypes).__wrapped__()

    assert response == 'Please enter a name.'


def test_post_archetypes_reports_duplicate_name_without_writing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(admin.archs, 'archetype_exists', lambda archetype_id: True)
    monkeypatch.setattr(admin.archs, 'name_exists', lambda name: True)
    monkeypatch.setattr(admin.archs, 'add', lambda *args: pytest.fail('Should not create a duplicate archetype'))
    monkeypatch.setattr(admin.rs, 'parse_cards_raw', lambda include, exclude: ([], []))
    monkeypatch.setattr(admin, 'edit_archetypes', lambda *args, **kwargs: '\n'.join(kwargs.get('add_errors') or []))

    with APP.test_request_context('/admin/archetypes/', method='POST', data={'create_archetype': '1', 'parent': '7', 'name': 'Delver'}):
        response = cast(Any, admin.post_archetypes).__wrapped__()

    assert response == 'An archetype named Delver already exists.'


def test_edit_archetypes_add_form_includes_rule_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deck, 'load_decks', lambda *args, **kwargs: [])
    monkeypatch.setattr(deck, 'load_queue_similarity', lambda decks: None)

    with APP.test_request_context('/admin/archetypes/'):
        html = EditArchetypes([], '', '').render_content()

    assert '<label for="description">Description</label>' in html
    assert '<section id="add-archetype">' in html
    assert '<form method="post" action="#add-archetype">' in html
    assert '<input type="hidden" name="create_archetype" value="1">' in html
    assert '<select name="parent" id="parent" required>' in html
    assert '<input type="text" name="name" id="name" value="" required>' in html
    assert '<label for="include">Must include</label>' in html
    assert '<textarea name="include" id="include"></textarea>' in html
    assert '<label for="exclude">Must not include</label>' in html
    assert '<textarea name="exclude" id="exclude"></textarea>' in html


def test_admin_menu_hides_admin_only_items_from_demimod() -> None:
    with APP.test_request_context('/admin/'):
        with APP.test_request_context('/admin/', environ_base={'HTTP_HOST': 'localhost'}):
            full_menu = admin.admin_menu()
            demimod_items = [item for item in full_menu if item.permission_required == 'demimod']
            admin_items = [item for item in full_menu if item.permission_required != 'demimod']
            assert len(demimod_items) > 0, 'Expected at least one demimod item'
            assert len(admin_items) > 0, 'Expected at least one admin-only item'


def test_all_admin_routes_require_permission() -> None:
    unprotected_routes = sorted({
        rule.rule
        for rule in APP.url_map.iter_rules()
        if rule.rule.startswith('/admin') and getattr(APP.view_functions[rule.endpoint], 'permission_required', None) not in {'admin', 'demimod'}
    })
    assert unprotected_routes == []


@pytest.mark.parametrize('path', ['/admin/banners/', '/admin/prizes/', '/admin/rotation/'])
def test_admin_information_pages_require_login(path: str) -> None:
    response = APP.test_client().get(path)
    assert response.status_code == 302
    assert response.location is not None
    assert response.location.startswith('/authenticate/?target=')


def test_post_rules_requires_archetype(monkeypatch: pytest.MonkeyPatch) -> None:
    def edit_rules(errors: list[str] | None = None) -> str:
        return EditRules(0, 0, [], [], [], [], [], [], errors).render_content()

    monkeypatch.setattr(admin, 'edit_rules', edit_rules)
    with APP.test_request_context('/admin/rules/', method='POST', data={'archetype_id': '', 'include': '4 Lightning Bolt'}):
        response = cast(Any, admin.post_rules).__wrapped__()
    assert 'Please select an archetype.' in response
    assert '<select name="archetype_id" required class="error" aria-describedby="archetype-error">' in response


def test_post_rules_validates_before_creating_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    def edit_rules(errors: list[str] | None = None) -> str:
        return EditRules(0, 0, [], [], [], [], [], [], errors).render_content()

    def parse_cards_raw(include: str, exclude: str) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
        raise InvalidDataException('Card not found in any deck: 4 Not a Card')

    monkeypatch.setattr(admin, 'edit_rules', edit_rules)
    monkeypatch.setattr(admin.rs, 'parse_cards_raw', parse_cards_raw)
    monkeypatch.setattr(admin.rs, 'add_rule', lambda archetype_id: pytest.fail('Should not create an invalid rule'))

    with APP.test_request_context('/admin/rules/', method='POST', data={'archetype_id': '7', 'include': '4 Not a Card'}):
        response = cast(Any, admin.post_rules).__wrapped__()

    assert 'Card not found in any deck: 4 Not a Card' in response


def test_post_rules_does_not_create_empty_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(admin, 'edit_rules', lambda errors=None: 'done')
    monkeypatch.setattr(admin.rs, 'parse_cards_raw', lambda include, exclude: ([], []))
    monkeypatch.setattr(admin.rs, 'add_rule', lambda archetype_id: pytest.fail('Should not create an empty rule'))

    with APP.test_request_context('/admin/rules/', method='POST', data={'archetype_id': '7'}):
        response = cast(Any, admin.post_rules).__wrapped__()

    assert response == 'done'


@pytest.mark.parametrize('action', ['add', 'change'])
@pytest.mark.parametrize('missing_score', ['left_games', 'right_games'])
def test_post_matches_requires_both_scores(monkeypatch: pytest.MonkeyPatch, action: str, missing_score: str) -> None:
    def edit_matches(form: EditMatchForm | None = None) -> str:
        assert form is not None
        return EditMatches(0, [], form).render_content()

    monkeypatch.setattr(admin, 'edit_matches', edit_matches)
    data = {'action': action, 'match_id': '3', 'left_id': '1', 'left_games': '2', 'right_id': '2', 'right_games': '1'}
    data.pop(missing_score)
    with APP.test_request_context('/admin/matches/', method='POST', data=data):
        response = cast(Any, admin.post_matches).__wrapped__()
    html = response.get_data(as_text=True)
    missing_side = missing_score.removesuffix('_games').replace('_', '-')
    present_score = '1' if missing_score == 'left_games' else '2'
    present_side = 'right' if missing_score == 'left_games' else 'left'
    assert f'<div id="{missing_side}-games-error" class="error">Please enter a score.</div>' in html
    assert f'<div id="{present_side}-games-error"' not in html
    assert f'name="{present_side}_games" value="{present_score}"' in html
    assert ' required' not in html


@pytest.mark.parametrize('action', ['add', 'change'])
@pytest.mark.parametrize('missing_deck', ['left_id', 'right_id'])
def test_post_matches_requires_both_decks(monkeypatch: pytest.MonkeyPatch, action: str, missing_deck: str) -> None:
    def edit_matches(form: EditMatchForm | None = None) -> str:
        assert form is not None
        return EditMatches(0, [], form).render_content()

    monkeypatch.setattr(admin, 'edit_matches', edit_matches)
    data = {'action': action, 'match_id': '3', 'left_id': '1', 'left_games': '2', 'right_id': '2', 'right_games': '1'}
    data.pop(missing_deck)
    with APP.test_request_context('/admin/matches/', method='POST', data=data):
        response = cast(Any, admin.post_matches).__wrapped__()
    html = response.get_data(as_text=True)
    missing_side = missing_deck.removesuffix('_id')
    present_side = 'right' if missing_deck == 'left_id' else 'left'
    assert f'<div id="{missing_side}-id-error" class="error">Please select a deck.</div>' in html
    assert f'<div id="{present_side}-id-error"' not in html
