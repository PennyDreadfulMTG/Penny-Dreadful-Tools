from decksite.data import deck
from magic.models import Card, Deck
from shared.container import Container


def test_set_colors() -> None:
    def card(name: str, mana_cost: str, oracle_text: str = '') -> Card:
        return Card(
            {
                'name': name,
                'mana_cost': mana_cost,
                'oracle_text': oracle_text,
            }
        )

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
