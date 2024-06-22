import pytest

from magic import database, mana


def test_simple() -> None:
    do_test('U', ['U'])
    do_test('{U}', ['U'])
    with pytest.raises(mana.InvalidManaCostException):
        do_test('Not a mana symbol sequence', [])


def test_twobrid() -> None:
    do_test('2/W2/W2/W', ['2/W', '2/W', '2/W'])


def test_twodigit() -> None:
    do_test('{15}', ['15'])


def test_gleemax() -> None:
    do_test('1000000', ['1000000'])


def test_x() -> None:
    do_test('X', ['X'])


def test_y() -> None:
    do_test('XYZ', ['X', 'Y', 'Z'])


def test_multicolor_x() -> None:
    do_test('XRB', ['X', 'R', 'B'])


def test_phyrexian() -> None:
    do_test('U/P', ['U/P'])


def test_porcelain_legionnaire() -> None:
    do_test('{2}{W/P}', ['2', 'W/P'])


def test_norns_annex() -> None:
    do_test('{3}{W/P}{W/P}', ['3', 'W/P', 'W/P'])


def test_slitherhead() -> None:
    do_test('{B/G}', ['B/G'])


def test_little_girl() -> None:
    do_test('{HW}', ['HW'])


def test_hybrid_phyrexian() -> None:
    do_test('{2}{G}{G/U/P}{U}', ['2', 'G', 'G/U/P', 'U'])


@pytest.mark.functional
def test_everything() -> None:
    rs = database.db().select('SELECT name, mana_cost FROM face')
    for row in rs:
        if row['mana_cost']:
            mana.parse(row['mana_cost'])


def test_colors() -> None:
    assert mana.colors(['9', 'W', 'W', 'R']) == {'required': {'W', 'R'}, 'also': set()}
    assert mana.colors(['2/W', 'G', 'X']) == {'required': {'G'}, 'also': {'W'}}
    assert mana.colors(['U/P', 'R/P']) == {'required': set(), 'also': {'U', 'R'}}
    assert mana.colors(['U', 'R', 'U/P', 'R/P']) == {'required': {'U', 'R'}, 'also': {'U', 'R'}}
    assert mana.colors(['X']) == {'required': set(), 'also': set()}
    assert mana.colors(['B/R']) == {'required': set(), 'also': {'B', 'R'}}
    assert mana.colors(['2', 'G', 'G/U/P', 'U']) == {'required': {'G', 'U'}, 'also': {'G', 'U'}}
    assert mana.colors(['W/B/P']) == {'required': set(), 'also': {'W', 'B'}}


def test_colored_symbols() -> None:
    assert mana.colored_symbols(['9', 'W', 'W', 'R']) == {'required': ['W', 'W', 'R'], 'also': []}
    assert mana.colored_symbols(['2/W', 'G', 'X']) == {'required': ['G'], 'also': ['W']}
    assert mana.colored_symbols(['U/P', 'R/P']) == {'required': [], 'also': ['U', 'R']}
    assert mana.colored_symbols(['X']) == {'required': [], 'also': []}
    assert mana.colored_symbols(['B/R']) == {'required': [], 'also': ['B', 'R']}
    assert mana.colored_symbols(['3', 'U', 'U']) == {'required': ['U', 'U'], 'also': []}
    assert mana.colored_symbols(['2', 'G', 'G/U/P', 'U']) == {'required': ['G', 'U'], 'also': ['G', 'U']}
    assert mana.colored_symbols(['W/B/P']) == {'required': [], 'also': ['W', 'B']}


def test_has_x() -> None:
    assert mana.has_x('{9}{X}')
    assert not mana.has_x('{1}{W}{W}')
    assert mana.has_x('{X}{Y}{R}')
    assert not mana.has_x('{C}')
    assert mana.has_x('{Y}{Z}')


def test_order() -> None:
    assert mana.order(['U']) == ['U']
    assert mana.order(['W', 'U', 'B']) == ['W', 'U', 'B']
    assert mana.order(['B', 'W', 'U']) == ['W', 'U', 'B']
    assert mana.order(['R', 'G']) == ['R', 'G']
    assert mana.order(['G', 'R']) == ['R', 'G']
    assert mana.order(['G', 'U']) == ['G', 'U']
    assert mana.order(['U', 'G']) == ['G', 'U']
    assert mana.order(['W', 'G']) == ['G', 'W']
    assert mana.order(['G', 'W']) == ['G', 'W']
    assert mana.order(['W', 'U', 'G']) == ['G', 'W', 'U']
    assert mana.order(['U', 'G', 'W']) == ['G', 'W', 'U']
    assert mana.order(['W', 'B', 'G']) == ['B', 'G', 'W']
    assert mana.order(['W', 'G', 'B']) == ['B', 'G', 'W']
    assert mana.order(['G', 'W', 'B']) == ['B', 'G', 'W']
    assert mana.order(['G', 'B', 'W']) == ['B', 'G', 'W']
    assert mana.order(['B', 'W', 'G']) == ['B', 'G', 'W']
    assert mana.order(['B', 'G', 'W']) == ['B', 'G', 'W']
    assert mana.order(['G', 'R', 'B']) == ['B', 'R', 'G']
    assert mana.order(['W', 'G', 'R', 'B']) == ['B', 'R', 'G', 'W']
    assert mana.order(['W', 'G', 'R', 'B']) == ['B', 'R', 'G', 'W']
    assert mana.order(['C']) == ['C']
    assert mana.order(['S']) == ['S']
    assert mana.order(['U', 'G']) == ['G', 'U']
    assert mana.order(['G', 'W', 'U']) == ['G', 'W', 'U']
    assert mana.order(['S', 'B', 'W']) == ['W', 'B', 'S']
    assert mana.order(['S', 'G', 'R']) == ['R', 'G', 'S']
    assert mana.order(['C', 'B', 'W']) == ['W', 'B', 'C']
    assert mana.order(['C', 'G', 'R']) == ['R', 'G', 'C']
    assert mana.order(['C', 'G', 'R', 'S']) == ['R', 'G', 'C', 'S']


def test_sort_score() -> None:
    assert mana.sort_score(['G', 'W', 'U']) > mana.sort_score(['G', 'U'])
    assert mana.sort_score(['B', 'R', 'G']) > mana.sort_score(['B', 'R'])
    assert mana.sort_score(['B', 'G']) > mana.sort_score(['G', 'W'])
    assert mana.sort_score(['C']) > mana.sort_score([])
    assert mana.sort_score(['W']) > mana.sort_score(['C'])
    assert mana.sort_score(['W', 'C']) > mana.sort_score(['W'])
    assert mana.sort_score(['W', 'S']) > mana.sort_score(['W', 'C'])
    assert mana.sort_score(['W', 'S', 'C']) > mana.sort_score(['W', 'C'])
    assert mana.sort_score(['U']) > mana.sort_score(['W', 'C'])
    assert mana.sort_score(['B', 'R', 'G', 'S']) > mana.sort_score(['B', 'R', 'G'])
    assert mana.sort_score(['B', 'R', 'G', 'S']) > mana.sort_score(['B', 'R', 'G', 'C'])
    assert mana.sort_score(['G']) > mana.sort_score(['C', 'W'])
    assert mana.sort_score(['W', 'U', 'B', 'R', 'G']) > mana.sort_score(['C', 'S', 'U', 'B', 'R', 'G'])


def test_colorless() -> None:
    assert mana.colored_symbols(['C']) == {'required': ['C'], 'also': []}


def test_snow() -> None:
    assert mana.colored_symbols(['S']) == {'required': ['S'], 'also': []}


def test_cmc() -> None:
    assert mana.cmc('{HW}') == 0.5
    assert mana.cmc('{HG}') == 0.5
    assert mana.cmc('{1}{U}{B}') == 3
    assert mana.cmc('{X}{R}') == 1
    assert mana.cmc('{2}{G}{G/U/P}{U}') == 5
    assert mana.cmc('{W/B/P}') == 1


def test_is_phyrexian() -> None:
    assert mana.phyrexian('R/P')
    assert mana.phyrexian('G/U/P')


def test_is_hybrid() -> None:
    assert mana.hybrid('G/U')
    assert not mana.hybrid('U/P')
    assert mana.hybrid('G/U/P')


def do_test(s: str, expected: list[str]) -> None:
    symbols = mana.parse(s)
    works = symbols == expected
    if not works:
        print(f'\nInput: {s}\nExpected: {expected}\n  Actual: {symbols}')
    assert works
