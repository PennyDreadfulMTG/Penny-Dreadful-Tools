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


def test_parse2():
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


def test_parse3():
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

def test_parse4():
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
        4 Scrabbling Claws





    """
    s = textwrap.dedent(s)
    d = decklist.parse(s)
    assert len(d['maindeck']) == 15
    assert len(d['sideboard']) == 7

def test_parse5():
    s = """
        4 Animist's Awakening
        4 Copperhorn Scout
        14 Forest
        4 Harvest Season
        4 Jaddi Offshoot
        4 Krosan Wayfarer
        4 Loam Dryad
        4 Nantuko Monastery
        4 Nest Invader
        4 Quest for Renewal
        4 Rofellos, Llanowar Emissary
        2 Sky Skiff
        4 Throne of the God-Pharaoh

        0 Villainous Wealth
    """
    s = textwrap.dedent(s)
    d = decklist.parse(s)
    print(d)
    assert len(d['maindeck']) == 13
    assert len(d['sideboard']) == 1
