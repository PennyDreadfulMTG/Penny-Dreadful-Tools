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
    output_format = kwargs['json']['output_config']['format']
    assert output_format['type'] == 'json_schema'
    confidence_schema = output_format['schema']['properties']['confidence']
    assert confidence_schema['type'] == 'integer'
    assert 'minimum' not in confidence_schema
    assert 'maximum' not in confidence_schema
    assert output_format['schema']['required'] == [
        'primary_plan',
        'intended_castable_colors',
        'evidence_cards',
        'competing_archetypes',
        'qualifier_check',
        'archetype',
        'confidence',
        'possible_new_variant',
        'variant_note',
    ]
    assert kwargs['json']['messages'] == [{'role': 'user', 'content': 'deck prompt'}]


def test_system_prompt_grounds_qualifiers_without_treating_colors_as_mechanical() -> None:
    assert 'never claim a profile card is in the submitted deck' in archetype_classifier.SYSTEM_PROMPT
    assert 'Infer intended castable colors from the manabase and normally cast spells' in archetype_classifier.SYSTEM_PROMPT
    assert 'off-color cheat or reanimation targets' in archetype_classifier.SYSTEM_PROMPT
    assert 'number of cards devoted to each defining package as a tiebreaker' in archetype_classifier.SYSTEM_PROMPT


@pytest.mark.parametrize(('reported', 'stored'), [(-10, 0), (92, 92), (120, 100)])
def test_classify_one_clamps_confidence(monkeypatch: pytest.MonkeyPatch, reported: int, stored: int) -> None:
    assign = mock.Mock()
    monkeypatch.setattr(archetype_classifier, '_shortlist', lambda _d, _meta: [(7, 'Aggro')])
    monkeypatch.setattr(archetype_classifier, '_deck_prompt', lambda _d, _candidates, _meta, _new_cards: 'prompt')
    monkeypatch.setattr(archetype_classifier, '_call', lambda _api_key, _model, _prompt: {
        'archetype': 'Aggro',
        'confidence': reported,
        'possible_new_variant': False,
        'variant_note': '',
    })
    monkeypatch.setattr(archetype_classifier.archetype, 'assign', assign)

    archetype_classifier._classify_one('secret', 'model', Container(id=1), {}, set())

    assign.assert_called_once_with(1, 7, None, False, stored)


def test_classify_one_rejects_unsupported_evidence(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assign = mock.Mock()
    monkeypatch.setattr(
        archetype_classifier,
        '_shortlist',
        lambda _d, _meta: [(7, 'Rakdos Reanimator'), (8, 'Traditional Reanimator')],
    )
    monkeypatch.setattr(archetype_classifier, '_deck_prompt', lambda _d, _candidates, _meta, _new_cards: 'prompt')
    monkeypatch.setattr(
        archetype_classifier,
        '_call',
        lambda _api_key, _model, _prompt: {
            'primary_plan': 'reanimate large creatures',
            'intended_castable_colors': ['White', 'Black', 'Red'],
            'evidence_cards': ['Priest of Fell Rites', 'Card From Candidate Profile'],
            'competing_archetypes': ['Rakdos Reanimator'],
            'qualifier_check': 'Rakdos is too narrow because the deck is built to cast white spells.',
            'archetype': 'Traditional Reanimator',
            'confidence': 96,
            'possible_new_variant': False,
            'variant_note': '',
        },
    )
    monkeypatch.setattr(archetype_classifier.archetype, 'assign', assign)
    monkeypatch.setattr(archetype_classifier.deck, 'similarity_score', lambda _d, _s: 0.72)
    caplog.set_level('INFO', logger=archetype_classifier.__name__)
    similar = Container(id=2, reviewed=True, archetype_id=7)
    source = Container(
        id=1,
        archetype_id=None,
        maindeck=[CardRef('Priest of Fell Rites', 4)],
        sideboard=[],
        similar_decks=[similar],
    )

    archetype_classifier._classify_one('secret', 'model', source, {}, set())

    assign.assert_called_once_with(1, 7, None, False, 72)
    assert "candidates=['Rakdos Reanimator', 'Traditional Reanimator']" in caplog.text
    assert "plan='reanimate large creatures'" in caplog.text
    assert "colors=['White', 'Black', 'Red']" in caplog.text
    assert "cited cards absent from submitted decklist: ['Card From Candidate Profile']; using nearest-deck fallback" in caplog.text


def test_call_logs_anthropic_error_response(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    response = mock.Mock(status_code=400, text='{"type":"error","error":{"message":"bad schema"}}')
    response.raise_for_status.side_effect = archetype_classifier.requests.HTTPError('400 Client Error')
    monkeypatch.setattr(archetype_classifier.requests, 'post', mock.Mock(return_value=response))

    with pytest.raises(archetype_classifier.requests.HTTPError):
        archetype_classifier._call('secret', 'model', 'prompt')

    assert 'bad schema' in caplog.text
