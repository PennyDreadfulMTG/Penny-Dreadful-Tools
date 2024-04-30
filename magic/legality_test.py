from magic import legality, seasons
from magic.models import CardRef, Deck


def test_legal_formats() -> None:
    season_name = seasons.current_season_name()

    d = Deck({'id': 0})
    d.maindeck = [CardRef('Swamp', 59)]
    d.sideboard = []
    assert len(d.all_cards()) == 59
    formats = legality.legal_formats(d)
    assert len(formats) == 0

    d.maindeck = [CardRef('Swamp', 60)]
    formats = legality.legal_formats(d)
    assert season_name in formats
    assert 'Legacy' in formats
    assert 'Penny Dreadful EMN' in formats
    assert 'Commander' not in formats

    formats = legality.legal_formats(d, {season_name})
    assert len(formats) == 1
    assert season_name in formats
    assert 'Legacy' not in formats

    d.maindeck = [CardRef('Swamp', 55), CardRef('Think Twice', 5)]
    assert len(d.all_cards()) == 60
    assert len(legality.legal_formats(d)) == 0

    d.maindeck = [CardRef('Swamp', 56), CardRef('Think Twice', 4)]
    formats = legality.legal_formats(d)
    assert 'Legacy' in formats
    assert 'Modern' in formats
    assert 'Oathbreaker' not in formats
    assert 'Duel' not in formats

    d.sideboard = [CardRef('Swamp', 15), CardRef('Think Twice', 1)]
    assert len(legality.legal_formats(d)) == 0

    d.maindeck = [CardRef('Swamp', 56), CardRef('Fork', 4)]
    d.sideboard = [CardRef('Swamp', 15)]
    formats = legality.legal_formats(d)
    assert 'Legacy' in formats
    assert 'Modern' not in formats
    assert 'Oathbreaker' not in formats

    d.maindeck = [CardRef('Swamp', 60)]
    d.sideboard = [CardRef('Swamp', 15)]
    formats = legality.legal_formats(d)
    assert 'Standard' in formats
    assert 'Modern' in formats
    assert 'Legacy' in formats
    assert 'Vintage' in formats
    assert season_name in formats
    assert 'Penny Dreadful EMN' in formats
    assert 'Duel' not in formats
