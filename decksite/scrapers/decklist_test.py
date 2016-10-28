import textwrap

from decksite.scrapers import decklist

def test_parse():
    s = """
        3 Barter in Blood
        4 Consume Spirit
        4 Demonic Rising
        4 Devour Flesh
        2 Distress
        2 Dread Statuary
        4 Haunted Plate Mail
        3 Homicidal Seclusion
        4 Hymn to Tourach
        2 Infest
        4 Quicksand
        4 Spawning Pool
        14 Swamp
        2 Ultimate Price
        4 Underworld Connections

        Sideboard
        1 Distress
        2 Dystopia
        1 Infest
        4 Memoricide
        2 Nature's Ruin
        1 Pharika's Cure
        4 Scrabbling Claws"""
    s = textwrap.dedent(s)
    d = decklist.parse(s)
    assert len(d['maindeck']) == 15
    assert len(d['sideboard']) == 7
