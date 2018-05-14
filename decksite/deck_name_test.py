from decksite import deck_name
from shared.container import Container


def test_normalize() -> None:
    d = Container({'original_name': 'Dimir Control', 'archetype_name': 'Control', 'colors': ['U', 'B']})
    assert deck_name.normalize(d) == 'Dimir Control'
    d.original_name = 'U/B Control'
    assert deck_name.normalize(d) == 'Dimir Control'
    d.original_name = 'dimir control'
    assert deck_name.normalize(d) == 'Dimir Control'
    d.original_name = 'U/B Reanimator'
    assert deck_name.normalize(d) == 'Dimir Reanimator'
    d.colors = ['B']
    d.original_name = 'penny dreadful black lifegain'
    assert deck_name.normalize(d) == 'Mono Black Lifegain'
    d.colors = ['G', 'U']
    d.original_name = 'biovisionary pd'
    assert deck_name.normalize(d) == 'Biovisionary'
    d.colors = ['R']
    d.archetype_name = 'Aggro'
    d.original_name = 'mono red ashling aggro'
    assert deck_name.normalize(d) == 'Mono Red Ashling Aggro'
    d.colors = ['W', 'U', 'B']
    d.archetype_name = 'Unclassified'
    d.original_name = 'penny dreadful esper mill'
    assert deck_name.normalize(d) == 'Esper Mill'
    d.colors = ['W', 'G']
    d.archetype_name = 'Aggro-Combo'
    d.original_name = 'penny dreadful gw tokens'
    assert deck_name.normalize(d) == 'Selesnya Tokens'
    d.colors = ['R', 'G', 'B']
    d.archetype_name = 'Control'
    d.original_name = 'Jund'
    assert deck_name.normalize(d) == 'Jund Control'
    d.archetype_name = None
    assert deck_name.normalize(d) == 'Jund'
    d.colors = ['R']
    d.original_name = 'RDW'
    assert deck_name.normalize(d) == 'Red Deck Wins'
    d.original_name = 'Red Deck Wins'
    assert deck_name.normalize(d) == 'Red Deck Wins'
    d.colors = ['W']
    d.original_name = 'WW'
    assert deck_name.normalize(d) == 'White Weenie'
    d.original_name = 'White Weenie'
    assert deck_name.normalize(d) == 'White Weenie'
    d.colors = ['B']
    d.original_name = '[pd] Mono B Control'
    assert deck_name.normalize(d) == 'Mono Black Control'
    d.colors = ['B', 'R']
    d.original_name = 'BR Control'
    assert deck_name.normalize(d) == 'Rakdos Control'
    d.colors = ['B']
    d.original_name = 'b '
    assert deck_name.normalize(d) == 'Mono Black'
    d.colors = ['U']
    d.original_name = 'muc'
    assert deck_name.normalize(d) == 'Mono Blue Control'
    d.colors = ['R']
    d.original_name = 'RDW23'
    assert deck_name.normalize(d) == 'Rdw23' # This isn't ideal but see BWWave for why it's probably right.
    d.colors = ['B']
    d.original_name = 'Mono B Aristocrats III'
    assert deck_name.normalize(d) == 'Mono Black Aristocrats III'
    d.original_name = 'Mono B Aristocrats VI'
    assert deck_name.normalize(d) == 'Mono Black Aristocrats VI'
    d.original_name = 'Suicide Black'
    assert deck_name.normalize(d) == 'Suicide Black'
    d.colors = ['R']
    d.original_name = 'Penny Dreadful Sunday RDW'
    assert deck_name.normalize(d) == 'Red Deck Wins'
    d.original_name = '[Pd][hou] Harvest Quest'
    assert deck_name.normalize(d) == 'Harvest Quest'
    d.original_name = 'Pd_Vehicles'
    assert deck_name.normalize(d) == 'Vehicles'
    d.original_name = 'better red than dead'
    assert deck_name.normalize(d) == 'Better Red Than Dead'
    d.original_name = 'week one rdw'
    assert deck_name.normalize(d) == 'Week One Red Deck Wins'
    d.colors = ['U', 'R']
    d.original_name = '.ur control'
    assert deck_name.normalize(d) == 'Izzet Control'
    d.colors = ['G']
    d.original_name = 'mono g aggro'
    assert deck_name.normalize(d) == 'Mono Green Aggro'
    d.original_name = 'monog ramp'
    assert deck_name.normalize(d) == 'Mono Green Ramp'
    d.original_name = 'Monogreen Creatures'
    assert deck_name.normalize(d) == 'Mono Green Creatures'
    d.colors = ['R']
    d.original_name = 'S6 red Deck Wins'
    assert deck_name.normalize(d) == 'Red Deck Wins'
    d.original_name = 'S6red Deck Wins'
    assert deck_name.normalize(d) == 'Red Deck Wins'
    d.colors = ['W']
    d.original_name = 'Mono-W Soldiers'
    assert deck_name.normalize(d) == 'Mono White Soldiers'
    d.original_name = 'BWWave'
    assert deck_name.normalize(d) == 'Bwwave' # Not ideal but ok.
    d.original_name = 'PD - Archfiend Cycling'
    assert deck_name.normalize(d) == 'Archfiend Cycling'
    d.original_name = 'a red deck but not a net deck'
    assert deck_name.normalize(d) == 'A Red Deck but Not a Net Deck'
    d.original_name = 'Better red than dead'
    assert deck_name.normalize(d) == 'Better Red Than Dead'
    d.original_name = "Is it Izzet or isn't it?"
    assert deck_name.normalize(d) == "Is It Izzet or Isn't It?"
    d.original_name = 'Rise like a golgari'
    d.colors = ['W', 'U', 'B', 'R', 'G']
    assert deck_name.normalize(d) == 'Rise Like a Golgari'
    d.original_name = 'BIG RED'
    assert deck_name.normalize(d) == 'Big Red'
    d.original_name = 'big Green'
    assert deck_name.normalize(d) == 'Big Green'
    d.colors = ['U', 'B']
    d.original_name = 'Black Power'
    assert deck_name.normalize(d) == 'Mono Black Power'
    d.colors = ['G']
    d.original_name = 'PD'
    assert deck_name.normalize(d) == 'Mono Green'
    d.colors = ['U', 'W']
    d.original_name = 'PD'
    d.archetype_name = 'Control'
    assert deck_name.normalize(d) == 'Azorius Control'

    # Undefined cases
    # d.original_name = 'U/B Aggro' when d.archetype_name = 'Control'
    # d.original_name = 'UB Control' when d.colors = ['U', 'B', 'R']

    # Cases that used to work well under strip-and-replace that no longer do
    # d.colors = ['W', 'G']
    # d.original_name = 'White Green'
    # d.archetype_name = 'Aggro'
    # assert deck_name.normalize(d) == 'Selesnya Aggro'
    # d.archetype_name = None
    # assert deck_name.normalize(d) == 'Selesnya'

def test_remove_pd() -> None:
    assert deck_name.remove_pd('Penny Dreadful Knights') == 'Knights'
    assert deck_name.remove_pd('biovisionary pd') == 'biovisionary'
    assert deck_name.remove_pd('[PD] Mono Black Control') == 'Mono Black Control'
