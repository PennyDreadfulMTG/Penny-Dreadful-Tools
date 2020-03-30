from decksite.data import elo


def test_elo() -> None:
    assert elo.expected(elo.STARTING_ELO, elo.STARTING_ELO) == 0.5
    assert elo.expected(10000, 1) > 0.99
    assert elo.expected(1, 10000) < 0.01
    assert elo.adjustment(elo.STARTING_ELO, elo.STARTING_ELO) == elo.K_FACTOR / 2
    assert elo.adjustment(10000, 1) == 1
    assert elo.adjustment(1, 10000) == elo.K_FACTOR
