import pytest

from decksite import form
from magic.models import Deck
from shared.pd_exception import InvalidDataException


def test_submitted_aliases_records_the_name_the_player_used(monkeypatch: pytest.MonkeyPatch) -> None:
    names = {
        'Origin of Spider-Man': 'Origin of Spider-Man',
        'A Most Helpful Weaver': 'Origin of Spider-Man',
    }
    monkeypatch.setattr(form.oracle, 'valid_name', names.__getitem__)

    aliases = form.submitted_aliases({
        'maindeck': {'Origin of Spider-Man': 3},
        'sideboard': {'A Most Helpful Weaver': 2},
    })

    assert aliases == {'Origin of Spider-Man': {'A Most Helpful Weaver'}}

def test_submitted_aliases_does_not_treat_a_normal_double_faced_name_as_an_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(form.oracle, 'valid_name', lambda _name: 'Peter Parker')

    aliases = form.submitted_aliases({
        'maindeck': {'Peter Parker // Amazing Spider-Man': 4},
        'sideboard': {},
    })

    assert aliases == {}

def test_submitted_aliases_ignores_invalid_names(monkeypatch: pytest.MonkeyPatch) -> None:
    def invalid_name(_name: str) -> str:
        raise InvalidDataException()

    monkeypatch.setattr(form.oracle, 'valid_name', invalid_name)

    assert form.submitted_aliases({'maindeck': {'Not a Card': 4}, 'sideboard': {}}) == {}

def test_card_messages_show_canonical_and_submitted_names() -> None:
    messages = {
        'Legality_Too_Many': {'Origin of Spider-Man', 'Swamp'},
    }
    aliases = {
        'Origin of Spider-Man': {'A Most Helpful Weaver'},
    }

    assert form.card_messages_with_submitted_aliases(messages, aliases) == {
        'Legality_Too_Many': {
            'Origin of Spider-Man (entered as A Most Helpful Weaver)',
            'Swamp',
        },
    }

def test_card_messages_list_multiple_submitted_aliases_deterministically() -> None:
    messages = {'Legality_Too_Many': {'Peter Parker'}}
    aliases = {
        'Peter Parker': {
            'Surris, Silk-Tech Vanguard',
            'Surris, Spidersilk Innovator',
        },
    }

    assert form.card_messages_with_submitted_aliases(messages, aliases) == {
        'Legality_Too_Many': {
            'Peter Parker (entered as Surris, Silk-Tech Vanguard; Surris, Spidersilk Innovator)',
        },
    }

def test_card_messages_preserve_bug_description_suffix() -> None:
    messages = {
        'Legality_Bugs': {'Bugged Card — It crashes the game'},
    }
    aliases = {
        'Bugged Card': {'An Alias'},
    }

    assert form.card_messages_with_submitted_aliases(messages, aliases) == {
        'Legality_Bugs': {
            'Bugged Card (entered as An Alias) — It crashes the game',
        },
    }

def test_card_messages_with_bug_description_no_alias() -> None:
    messages = {
        'Warnings_Bugs': {'Some Card — Causes life total corruption'},
    }
    aliases: dict[str, set[str]] = {}

    assert form.card_messages_with_submitted_aliases(messages, aliases) == {
        'Warnings_Bugs': {
            'Some Card — Causes life total corruption',
        },
    }

def test_legality_validation_uses_the_submitted_alias_in_its_message(monkeypatch: pytest.MonkeyPatch) -> None:
    decklist_form = form.DecklistForm.__new__(form.DecklistForm)
    decklist_form.cards = {
        'maindeck': {'A Most Helpful Weaver': 5, 'Swamp': 55},
        'sideboard': {},
    }
    decklist_form.deck = Deck({'maindeck': [], 'sideboard': []})
    decklist_form.errors = {}
    decklist_form.warnings = {}
    decklist_form.card_errors = {}
    decklist_form.card_warnings = {}

    monkeypatch.setattr(
        form.oracle,
        'valid_name',
        lambda name: 'Origin of Spider-Man' if name == 'A Most Helpful Weaver' else name,
    )
    monkeypatch.setattr(form.seasons, 'current_season_name', lambda: 'Penny Dreadful Test')

    def illegal_deck(_deck: Deck, _formats: set[str] | None, errors: dict[str, dict[str, set[str]]]) -> set[str]:
        errors['Penny Dreadful Test'] = {'Legality_Too_Many': {'Origin of Spider-Man'}}
        return set()

    monkeypatch.setattr(form.legality, 'legal_formats', illegal_deck)

    decklist_form.check_deck_legality()

    assert decklist_form.card_errors == {
        'Legality_Too_Many': {
            'Origin of Spider-Man (entered as A Most Helpful Weaver)',
        },
    }
