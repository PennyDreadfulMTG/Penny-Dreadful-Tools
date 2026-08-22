from unittest import mock

from decksite.data import deck
from magic.models import Card, Deck
from shared.container import Container


def test_maybe_regenerate_symbols_font_for_unusual_character() -> None:
    with (
        mock.patch.object(deck, 'db') as db,
        mock.patch.object(deck.fonts, 'regenerate_symbols_font') as regenerate_symbols_font,
    ):
        deck.maybe_regenerate_symbols_font('Sparkles ✨')

    db.return_value.get_lock.assert_called_once_with('font_generation', 60 * 15)
    regenerate_symbols_font.assert_called_once_with()
    db.return_value.release_lock.assert_called_once_with('font_generation')


def test_maybe_regenerate_symbols_font_ignores_latin_1() -> None:
    with (
        mock.patch.object(deck, 'db') as db,
        mock.patch.object(deck.fonts, 'regenerate_symbols_font') as regenerate_symbols_font,
    ):
        deck.maybe_regenerate_symbols_font('Déjà Vu')

    db.assert_not_called()
    regenerate_symbols_font.assert_not_called()


def test_set_colors() -> None:
    def card(name: str, mana_cost: str, oracle_text: str = '') -> Card:
        return Card({
            'name': name,
            'mana_cost': mana_cost,
            'oracle_text': oracle_text,
        })

    bop = card('Birds of Paradise', '{G}')
    bbe = card('Bloodbraid Elf', '{2}{R}{G}')
    life_death = card('Life // Death', '{G}|{1}{B}')
    rav_trap = card('Ravenous Trap', '{2}{B}{B}', oracle_text="If an opponent had three or more cards put into their graveyard from anywhere this turn, you may pay {0} rather than pay this spell's mana cost.")
    valentin = card('Valentin, Dean of the Vein', '{B}|{2}{G}{G}')
    finks = card('Kitchen Finks', '{1}{G/W}{G/W}')
    tests = [
        ([], []),
        ([bop], ['G']),
        ([bbe], ['R', 'G']),
        # split should be ignored
        ([bop, bbe, life_death], ['R', 'G']),
        # ravenous trap should be ignored
        ([bop, bbe, rav_trap], ['R', 'G']),
        # modal_dfc should be ignored
        ([bop, bbe, valentin], ['R', 'G']),
        # hybrid should be ignored
        ([bop, bbe, valentin, finks], ['R', 'G']),
    ]
    for cs, output in tests:
        d = Deck({'maindeck': [Container({'card': c, 'n': 4}) for c in cs], 'sideboard': []})
        deck.set_colors(d)
        assert d.colors == output
