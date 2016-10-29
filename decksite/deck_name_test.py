from munch import Munch

from decksite import deck_name

def test_normalize():
    d = Munch({'name': 'Dimir Control', 'archetype': 'Control', 'colors': ['U', 'B']})
    assert deck_name.normalize(d) == '{U}{B} Control'
    d.name = 'U/B Control'
    assert deck_name.normalize(d) == '{U}{B} Control'
    d.name = 'dimir control'
    assert deck_name.normalize(d) == '{U}{B} Control'
    d.name = 'U/B Reanimator'
    assert deck_name.normalize(d) == '{U}{B} Reanimator'
    d.colors = ['B']
    d.name = 'penny dreadful black lifegain'
    assert deck_name.normalize(d) == '{B} Lifegain'
    d.colors = ['G', 'U']
    d.name = 'biovisionary pd'
    assert deck_name.normalize(d) == '{G}{U} Biovisionary'
    d.colors = ['R']
    d.archetype = 'Aggro'
    d.name = 'mono red ashling aggro'
    assert deck_name.normalize(d) == '{R} Ashling Aggro'
    d.colors = ['W', 'U', 'B']
    d.archetype = 'Unclassified'
    d.name = 'penny dreadful esper mill'
    assert deck_name.normalize(d) == '{W}{U}{B} Mill'
    d.colors = ['W', 'G']
    d.archetype = 'Aggro-Combo'
    d.name = 'penny dreadful gw tokens'
    assert deck_name.normalize(d) == '{G}{W} Tokens'
    d.colors = ['R', 'G', 'B']
    d.archetype = 'Control'
    d.name = 'Jund'
    assert deck_name.normalize(d) == '{B}{R}{G} Control'
    d.archetype = None
    assert deck_name.normalize(d) == '{B}{R}{G} Jund'
    d.colors = ['W', 'G']
    d.name = 'White Green'
    d.archetype = 'Aggro'
    assert deck_name.normalize(d) == '{G}{W} Aggro'
    d.archetype = None
    assert deck_name.normalize(d) == '{G}{W} Selesnya'

    # Undefined cases
    # d.name = 'U/B Aggro' when d.archetype = 'Control'
    # d.name = 'UB Control' when d.colors = ['U', 'B', 'R']

def test_remove_pd():
    assert deck_name.remove_pd('Penny Dreadful Knights') == 'Knights'
    assert deck_name.remove_pd('biovisionary pd') == 'biovisionary'
