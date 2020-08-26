from typing import List

import pytest

from decksite import deck_name
from shared.container import Container
from shared.pd_exception import InvalidDataException

TESTDATA = [
    ('Dimir Control', 'Dimir Control', ['U', 'B'], 'Control'),
    ('U/B Control', 'Dimir Control', ['U', 'B'], 'Control'),
    ('dimir Control', 'Dimir Control', ['U', 'B'], 'Control'),
    ('U/B Reanimator', 'Dimir Reanimator', ['U', 'B'], 'Control'),
    ('penny dreadful black lifegain', 'Mono Black Lifegain', ['B'], 'Control'),
    ('biovisionary pd', 'Biovisionary', ['G', 'U'], 'Control'),
    ('mono red ashling aggro', 'Mono Red Ashling Aggro', ['R'], 'Aggro'),
    ('penny dreadful esper mill', 'Esper Mill', ['W', 'U', 'B'], 'Unclassified'),
    ('penny dreadful gw tokens', 'Selesnya Tokens', ['W', 'G'], 'Aggro-Combo'),
    ('Jund', 'Jund Control', ['R', 'G', 'B'], 'Control'),
    ('Jund', 'Jund', ['R', 'G', 'B'], None),
    ('RDW', 'Red Deck Wins', ['R'], 'Aggro'),
    ('Red Deck Wins', 'Red Deck Wins', ['R'], 'Aggro'),
    ('WW', 'White Weenie', ['W'], 'Aggro'),
    ('White Weenie', 'White Weenie', ['W'], 'Aggro'),
    ('[pd] Mono B Control', 'Mono Black Control', ['B'], 'Control'),
    ('BR Control', 'Rakdos Control', ['B', 'R'], 'Control'),
    ('b ', 'Mono Black', ['B'], None),
    ('muc', 'Mono Blue Control', ['U'], None),
    ('RDW23', 'Rdw23', ['R'], None), # This isn't ideal but see BWWave for why it's probably right.
    ('Mono B Aristocrats III', 'Mono Black Aristocrats III', ['B'], None),
    ('Mono B Aristocrats IV', 'Mono Black Aristocrats IV', ['B'], None),
    ('Suicide Black', 'Suicide Black', ['B'], None),
    ('Penny Dreadful Sunday RDW', 'Red Deck Wins', ['R'], None),
    ('[Pd][hou] Harvest Quest', 'Harvest Quest', None, None),
    ('Pd_Vehicles', 'Vehicles', None, None),
    ('better red than dead', 'Better Red Than Dead', ['R'], None),
    ('week one rdw', 'Week One Red Deck Wins', ['R'], None),
    ('.ur control', 'Izzet Control', ['U', 'R'], None),
    ('mono g aggro', 'Mono Green Aggro', ['G'], 'Aggro'),
    ('monog ramp', 'Mono Green Ramp', ['G'], 'Aggro'),
    ('Monogreen Creatures', 'Green Creatures', ['G', 'W'], None),
    ('S6 red Deck Wins', 'Red Deck Wins', ['R'], None),
    ('S6red Deck Wins', 'Red Deck Wins', ['R'], None),
    ('Mono-W Soldiers', 'Mono White Soldiers', ['W'], None),
    ('BWWave', 'Bwwave', ['W'], None), # Not ideal but ok.
    ('PD - Archfiend Cycling', 'Archfiend Cycling', None, None),
    ('a red deck but not a net deck', 'A Red Deck but Not a Net Deck', None, None),
    ('Better red than dead', 'Better Red Than Dead', None, None),
    ("Is it Izzet or isn't it?", "Is It Izzet or Isn't It?", None, None),
    ('Rise like a golgari', 'Rise Like a Golgari', ['W', 'U', 'B', 'R', 'G'], None),
    ('BIG RED', 'Big Red', None, None),
    ('big Green', 'Big Green', None, None),
    ('Black Power', 'Black Power', ['U', 'B'], None),
    ('PD', 'Mono Green', ['G'], None),
    ('PD', 'Azorius Control', ['U', 'W'], 'Control'),
    ('PD', 'Azorius', ['U', 'W'], 'Unclassified'),
    ('Bant #Value', 'Bant Yisan-Prophet', ['G', 'U', 'W'], 'Yisan-Prophet'),
    ('Yore-Tiller Control', 'WUBR Control', ['W', 'U', 'B', 'R'], 'Control'),
    ('Dimir', 'Dimir Control', ['U', 'B'], 'Control'),
    ('Basic Red Bitch', 'Basic Red', ['R'], 'Aggro'),
    ('black white aristocrats', 'Orzhov Aristocrats', ['B', 'W'], 'Aggro-Combo'),
    ('Yore-Tiller Control', 'WUBR Control', ['W', 'U', 'B', 'R'], 'Control'),
    ('WUBR Control', 'WUBR Control', ['W', 'U', 'B', 'R'], 'Control'),
    ('RBUW Control', 'WUBR Control', ['W', 'U', 'B', 'R'], 'Control'),
    ('White Jund', 'White Jund', ['B', 'R', 'G', 'W'], 'White Jund'),
    ('White Jund', 'BRGW', ['B', 'R', 'G', 'W'], None),
    ('ゼウスサイクリング', 'Sultai New Perspectives', ['U', 'G', 'B'], 'New Perspectives'),
    ('$', 'UBRG Necrotic Ooze Combo', ['U', 'B', 'R', 'G'], 'Necrotic Ooze Combo'),
    ('White Green', 'Selesnya Aggro', ['W', 'G'], 'Aggro'),
    ('White Green', 'Selesnya', ['W', 'G'], None),
    ('RG Energy', 'Gruul Energy', ['R', 'G'], 'Pummeler'),
    ('Black/Red', 'Rakdos', ['B', 'R'], None),
    ('Blue Burn', 'Blue Burn', ['U', 'R'], None),
    ('WB', 'Orzhov Aristocrats', ['W', 'B'], 'Orzhov Aristocrats'),
    ("Bob's R Us", "Bob's R Us", ['B'], 'Mono Black Aggro'),
    ('PD ""Affinity""', '""Affinity""', ['W'], 'Tempered Steel'),
    ('PD10 Killer', 'Killer', ['R'], 'Red Deck Wins'),
    ('PD-10 Killer', 'Killer', ['R'], 'Red Deck Wins'),
    ('PD-10 Killer', 'Killer', ['R'], 'Red Deck Wins'),
    ('Deck - Mono Black Aristocrats (1)', 'Mono Black Aristocrats (1)', ['B'], 'Mono Black Aristocrats'),
    ('PD-GB', 'Golgari the Rock', ['G', 'B'], 'The Rock'),
    ('PD 11 WW', 'White Weenie', ['W'], None),
    ('Bad Esper 2.0', 'Bad Esper 2.0', ['W', 'U', 'B'], 'Esper Control'),
    ('B', 'Mono Black', ['B'], 'Zombies'),
    ('Manaless Dredge', 'Manaless Dredge', ['B'], 'Graveyard Value'),
    ('Deep Anal', 'Deep', ['U'], 'Control'),
    ('Supremacia Ariana', 'Mono White', ['W'], None),
    ('Blue Bois', 'Blue Bois', ['U', 'B'], None),
    ('Analog Drake', 'Analog Drake', ['U', 'W'], 'Peregrine Drake'),
    ('R Deck Wins', 'Red Deck Wins', ['R'], 'Red Deck Wins'),
    ('HAND　DEATH', 'Hand Death', ['B'], 'Mono Black Midrange'),
    ('(Penny) Boros Soldiers', 'Boros Soldiers', ['W', 'R'], 'Soldiers'),
    ('Red Deck Wins byvci', 'Red Deck Wins Byvci', ['R'], 'Red Deck Wins'),
    ('ABZAN - PD', 'Abzan Lifegain Midrange', ['W', 'B', 'G'], 'Lifegain Midrange'),
    ('Food - PD', 'Food', ['B', 'R', 'G'], 'Food'),
    ('Storm (PD S16)', 'Storm', ['U', 'B'], 'Storm'),
    ('Black-Red Midrange', 'Rakdos Midrange', ['R', 'B'], 'Rakdos Midrange'),
    ('Happy B DAY Adriana', 'Happy B Day Adriana', ['W', 'R'], 'AggroSlide'),
    ('braids b', 'Braids Black', ['B'], 'Midrange'),
    ('[Penny Dreadful] UR Cycling', 'Izzet Cycling', ['U', 'R'], 'Midrange'),
    ('Penny-Zombies', 'Zombies', ['B'], 'Zombies')
]

@pytest.mark.parametrize('original_name,expected,colors,archetype_name', TESTDATA)
def test_normalize(original_name: str, expected: str, colors: List[str], archetype_name: str) -> None:
    d = Container({'original_name': original_name,
                   'archetype_name': archetype_name,
                   'colors': colors or []})
    assert deck_name.normalize(d) == expected

def test_remove_pd() -> None:
    assert deck_name.remove_pd('Penny Dreadful Knights') == 'Knights'
    assert deck_name.remove_pd('biovisionary pd') == 'biovisionary'
    assert deck_name.remove_pd('[PD] Mono Black Control') == 'Mono Black Control'
    assert deck_name.remove_pd('(Penny) Boros Soliders') == 'Boros Soliders'

def test_invalid_color() -> None:
    d = Container({'original_name': 'PD',
                   'archetype_name': 'Control',
                   'colors': ['U', 'X']})
    try:
        deck_name.normalize(d)
        assert False
    except InvalidDataException:
        assert True

def test_canonicalize_colors() -> None:
    assert deck_name.canonicalize_colors([]) == set()
    assert deck_name.canonicalize_colors(['White', 'Black', 'Orzhov', 'Abzan']) == {'B', 'G', 'W'}
    assert deck_name.canonicalize_colors(['White', 'White', 'White']) == {'W'}

def test_normalize_colors() -> None:
    assert deck_name.normalize_colors('Braids B', ['B']) == 'Braids Black'
    assert deck_name.normalize_colors('Haha Zombie Army Goes BR', ['B', 'R']) == 'Haha Zombie Army Goes Rakdos'
    assert deck_name.normalize_colors('Haha Zombie Army Goes Brrr', ['B', 'R']) == 'Haha Zombie Army Goes Brrr'
    assert deck_name.normalize_colors('Haha Zombie Army Goes Brrr BR', ['B', 'R']) == 'Haha Zombie Army Goes Brrr Rakdos'
    assert deck_name.normalize_colors('Meme Deck uwu', ['B', 'R']) == 'Meme Deck uwu'
