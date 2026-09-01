import datetime
from unittest import mock

import pytest

from decksite.data import archetype_classifier
from magic.models import CardRef
from shared.container import Container


def test_run_does_no_expensive_work_for_an_empty_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    calculate_similar_decks = mock.Mock()
    monkeypatch.setattr(archetype_classifier.deck, 'load_decks', lambda *args, **kwargs: ([], 0))
    monkeypatch.setattr(archetype_classifier.deck, 'calculate_similar_decks', calculate_similar_decks)

    archetype_classifier.run()

    calculate_similar_decks.assert_not_called()


def test_run_without_an_api_key_preserves_the_old_guesser(monkeypatch: pytest.MonkeyPatch) -> None:
    source = Container(id=1, archetype_id=None, maindeck=[CardRef('Shared Card', 4)])
    similar = Container(id=2, reviewed=True, archetype_id=7, maindeck=[CardRef('Shared Card', 4)])
    assign = mock.Mock()

    def calculate_similar_decks(decks: list[Container]) -> None:
        decks[0].similar_decks = [similar]

    monkeypatch.setattr(archetype_classifier.deck, 'load_decks', lambda *args, **kwargs: ([source], 1))
    monkeypatch.setattr(archetype_classifier.deck, 'calculate_similar_decks', calculate_similar_decks)
    monkeypatch.setattr(archetype_classifier.configuration, 'get_optional_str', lambda _key: None)
    monkeypatch.setattr(archetype_classifier.archetype, 'assign', assign)

    archetype_classifier.run()

    assign.assert_called_once_with(1, 7, None, False, 100)


def test_load_top_cards_uses_daily_preaggregation(monkeypatch: pytest.MonkeyPatch) -> None:
    database = mock.Mock()
    database.select.return_value = [
        {'aid': 1, 'card': 'Signature Card', 'n': 8},
        {'aid': 1, 'card': 'Support Card', 'n': 3},
    ]
    monkeypatch.setattr(archetype_classifier, 'db', lambda: database)
    meta: archetype_classifier.Metadata = {
        1: {'name': 'Test Archetype', 'description': '', 'lineage': [], 'top_cards': []},
    }

    archetype_classifier._load_top_cards(meta, '1')

    sql = database.select.call_args.args[0]
    assert '_season_archetype_card_count' in sql
    assert 'JOIN deck ' not in sql
    assert 'JOIN deck_card ' not in sql
    assert meta[1]['top_cards'] == ['Signature Card', 'Support Card']


def test_new_cards_query_is_bounded_to_cards_in_the_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    rotation = datetime.datetime(2026, 8, 21, tzinfo=datetime.UTC)
    cards = {
        'New Card': Container(id=11, name='New Card'),
        'Old Card': Container(id=22, name='Old Card'),
    }
    database = mock.Mock()
    database.select.return_value = [{'card_id': 11, 'released_at': int(rotation.timestamp())}]
    monkeypatch.setattr(archetype_classifier.seasons, 'last_rotation', lambda: rotation)
    monkeypatch.setattr(archetype_classifier.oracle, 'cards_by_name', lambda: cards)
    monkeypatch.setattr(archetype_classifier, 'magic_db', lambda: database)
    decks = [Container(maindeck=[CardRef('New Card', 4), CardRef('Old Card', 4)])]

    assert archetype_classifier._new_cards_this_season(decks) == {'New Card'}

    sql, args = database.select.call_args.args
    assert 'FROM printing AS p' in sql
    assert 'deck_card' not in sql
    assert args == [11, 22, int(rotation.timestamp())]


def test_call_requests_structured_json(monkeypatch: pytest.MonkeyPatch) -> None:
    response = mock.Mock()
    response.json.return_value = {
        'stop_reason': 'end_turn',
        'content': [{'type': 'text', 'text': '{"archetype":"Aggro","confidence":92,"possible_new_variant":false,"variant_note":""}'}],
    }
    post = mock.Mock(return_value=response)
    monkeypatch.setattr(archetype_classifier.requests, 'post', post)

    assert archetype_classifier._call('secret', 'claude-haiku-4-5', 'deck prompt') == {
        'archetype': 'Aggro',
        'confidence': 92,
        'possible_new_variant': False,
        'variant_note': '',
    }

    response.raise_for_status.assert_called_once_with()
    _, kwargs = post.call_args
    assert kwargs['headers']['x-api-key'] == 'secret'
    assert kwargs['json']['output_config']['format']['type'] == 'json_schema'
    assert kwargs['json']['messages'] == [{'role': 'user', 'content': 'deck prompt'}]
