from typing import List

import pytest

from find import search
from find.search import InvalidValueException
from magic.database import db

# Some of these tests only work hooked up to a cards db, and are thus marked functional. They are fast, though, and you should run them if editing card search.
# $ python3 dev.py test find

def test_match() -> None:
    assert search.Key.match('c')
    assert search.Key.match('mana')
    assert not search.Key.match('z')
    assert not search.Key.match('')
    assert not search.Key.match(' ')
    assert not search.Criterion.match('magic:2uu')
    assert search.Criterion.match('tou>2')

# START Tests from https://scryfall.com/docs/syntax

@pytest.mark.functional
def test_colors_and_color_identity() -> None:
    s = 'c:rg'
    do_functional_test(s, ['Animar, Soul of Elements', 'Boggart Ram-Gang', 'Progenitus'], ['About Face', 'Cinder Glade', 'Lupine Prototype', 'Sylvan Library'])
    s = 'color>=uw -c:red'
    do_functional_test(s, ['Absorb', 'Arcades Sabboth', 'Bant Sureblade', 'Worldpurge'], ['Brainstorm', 'Mantis Rider', 'Karn Liberated'])
    s = 'id<=esper t:instant'
    do_functional_test(s, ['Abeyance', 'Abjure', 'Absorb', 'Ad Nauseam', 'Batwing Brume', 'Warping Wail'], ['Act of Aggression', 'Inside Out', 'Jilt'])
    s = 'id<=ESPER t:instant'
    do_functional_test(s, ['Abeyance', 'Abjure', 'Absorb', 'Ad Nauseam', 'Batwing Brume', 'Warping Wail'], ['Act of Aggression', 'Inside Out', 'Jilt'])
    s = 'c:m'
    do_functional_test(s, ['Bant Charm', 'Murderous Redcap'], ['Izzet Signet', 'Lightning Bolt', 'Spectral Procession'])
    s = 'c=br'
    do_functional_test(s, ['Murderous Redcap', 'Terminate'], ['Cruel Ultimatum', 'Fires of Undeath', 'Hymn to Tourach', 'Lightning Bolt', 'Rakdos Signet'])
    s = 'id:c t:land'
    do_functional_test(s, ['Ancient Tomb', 'Wastes'], ['Academy Ruins', 'Island'])

@pytest.mark.functional
def test_types() -> None:
    s = 't:merfolk t:legend'
    do_functional_test(s, ['Emry, Lurker of the Loch', 'Sygg, River Cutthroat'], ['Hullbreacher', 'Ragavan, Nimble Pilferer'])
    s = 't:goblin -t:creature'
    do_functional_test(s, ['Tarfire', 'Warren Weirding'], ['Goblin Bombardment', 'Lightning Bolt', 'Skirk Prospector'])

@pytest.mark.functional
def test_card_text() -> None:
    s = 'o:draw o:creature'
    do_functional_test(s, ['Edric, Spymaster of Trest', 'Grim Backwoods', 'Mystic Remora'], ['Ancestral Recall', 'Honor of the Pure'])
    s = 'o:"~ enters the battlefield tapped"'
    do_functional_test(s, ['Arcane Sanctum', 'Diregraf Ghoul', 'Golgari Guildgate'], ['Tarmogoyf'])

@pytest.mark.functional
def test_mana_costs() -> None:
    s = 'mana:{G}{U}'
    do_functional_test(s, ['Omnath, Locus of Creation', 'Ice-Fang Coatl'], ['Breeding Pool', 'Slippery Bogle'])

    # https://github.com/PennyDreadfulMTG/Penny-Dreadful-Tools/issues/8969
    # s = 'm:2WW'
    # do_functional_test(s, ["Emeria's Call", 'Solitude'], ['Karoo', 'Spectral Procession'])
    # s = 'm>3WU'
    # do_functional_test(s, ['Drogskol Reaver', 'Sphinx of the Steel Wind'], ['Angel of the Dire Hour', 'Fractured Identity'])

    s = 'm:{R/P}'
    do_functional_test(s, ['Gut Shot', 'Slash Panther'], ['Dismember', 'Lightning Bolt'])
    s = 'c:u cmc=5'
    do_functional_test(s, ['Force of Will', 'Fractured Identity'], ['Goldspan Dragon', 'Omnath, Locus of Creation'])

    # https://github.com/PennyDreadfulMTG/Penny-Dreadful-Tools/issues/8968
    # s = 'devotion:{u/b}{u/b}{u/b}'
    # do_functional_test(s, ['Ashemnoor Gouger', 'Niv-Mizzet Parun', 'Omniscience', 'Phrexian Obliterator', 'Progenitus'], ['Cunning Nightbonger', 'Watery Grave'])

    # https://github.com/PennyDreadfulMTG/Penny-Dreadful-Tools/issues/8618
    # s = 'produces=wu'
    # do_functional_test(s, ['Azorius Signet', 'Celestial Colonnade'], ['Birds of Paradise', 'Teferi, Time Raveler'])

@pytest.mark.functional
def test_power_toughness_and_loyalty() -> None:
    s = 'pow>=8'
    do_functional_test(s, ["Death's Shadow", 'Dragonlord Atarka', 'Emrakul, the Aeons Torn'], ['Mortivore', 'Swamp', 'Tarmogoyf', 'Wild Nacatl'])

    # https://github.com/PennyDreadfulMTG/Penny-Dreadful-Tools/issues/8970
    # s = 'pow>tou c:w t:creature'
    # do_functional_test(s, ["Kataki, War's Wage", 'Knight of Autumn'], ['Bonecrusher Giant', 'Hullbreacher', 'Swamp'])

    s = 't:planeswalker loy=3'
    do_functional_test(s, ['Jace, the Mind Sculptor', 'Liliana of the Veil'], ['Karn, the Great Creator', 'Mountain', 'Progenitus'])

def test_multi_faced_cards() -> None:
    s = 'is:meld'
    do_functional_test(s, ['Hanweir Battlements', 'Hanweir Garrison'], ['Hanweir, the Writhing Township'])
    s = 'is:split'
    do_functional_test(s, ['Driven // Despair', 'Fire // Ice', 'Wear // Tear'], ['Budoka Gardener', 'Hanweir Garrison'])

# END Tests from https://scryfall.com/docs/syntax

@pytest.mark.functional
def test_edition_functional() -> None:
    do_functional_test('e:ktk', ['Flooded Strand', 'Treasure Cruise', 'Zurgo Helmsmasher'], ['Life from the Loam', 'Scalding Tarn', 'Zurgo Bellstriker'])

def test_edition() -> None:
    do_test('e:ktk', "(c.id IN (SELECT card_id FROM printing WHERE set_id IN (SELECT id FROM `set` WHERE name LIKE '%%ktk%%' OR code = 'ktk')))")

def test_special_chars() -> None:
    do_test('o:a_c%', "(oracle_text LIKE '%%a\\_c\\%%%%')")

@pytest.mark.functional
def test_tilde_functional() -> None:
    do_functional_test('o:"sacrifice ~"', ['Abandoned Outpost', 'Black Lotus'], ['Cartel Aristocrat', 'Life from the Loam'])

def test_tilde() -> None:
    expected = "(oracle_text LIKE CONCAT('%%sacrifice ', name, '%%'))"
    do_test('o:"sacrifice ~"', expected)

@pytest.mark.functional
def test_double_tilde_functional() -> None:
    do_functional_test('o:"sacrifice ~: ~ deals 2 damage to any target"', ['Blazing Torch', 'Inferno Fist'], ['Black Lotus', 'Cartel Aristocrat'])

def test_double_tilde() -> None:
    expected = "(oracle_text LIKE CONCAT('%%sacrifice ', name, ': ', name, ' deals 2 damage to any target%%'))"
    do_test('o:"sacrifice ~: ~ deals 2 damage to any target"', expected)

@pytest.mark.functional
def test_only_multicolored_functional() -> None:
    do_functional_test('c:m', ['Bant Charm', 'Murderous Redcap'], ['Door to Nothingness', 'Fires of Undeath', 'Lightning Bolt'])

def test_only_multicolored() -> None:
    do_test('c:m', '(c.id IN (SELECT card_id FROM card_color GROUP BY card_id HAVING COUNT(card_id) >= 2))')

def test_multicolored_with_other_colors() -> None:
    found = False
    try:
        do_test('c:bm', '')
    except InvalidValueException:
        found = True
    assert found

@pytest.mark.functional
def test_multicolored_coloridentity_functional() -> None:
    do_functional_test('ci>=b', ['Dark Ritual', 'Golos, Tireless Pilgrim', 'Murderous Redcap', 'Swamp'], ['Black Lotus', 'Daze', 'Plains'])

def test_multicolored_coloridentity() -> None:
    do_test('ci>=b', '((c.id IN (SELECT card_id FROM card_color_identity WHERE color_id = 3)))')

@pytest.mark.functional
def test_exclusivemulitcolored_same_functional() -> None:
    do_functional_test('ci!b', ['Dark Ritual', 'Swamp'], ['Black Lotus', 'Golos, Tireless Pilgrim', 'Muderous Redcap'])

def test_exclusivemulitcolored_same() -> None:
    do_test('ci!b', '((c.id IN (SELECT card_id FROM card_color_identity WHERE color_id = 3))) AND (c.id IN (SELECT card_id FROM card_color_identity GROUP BY card_id HAVING COUNT(card_id) <= 1))')

def test_mulitcolored_multiple() -> None:
    do_test('c=br', '((c.id IN (SELECT card_id FROM card_color WHERE color_id = 3))) AND ((c.id IN (SELECT card_id FROM card_color WHERE color_id = 4))) AND (c.id IN (SELECT card_id FROM card_color GROUP BY card_id HAVING COUNT(card_id) <= 2))')

def test_multicolored_exclusive_functional() -> None:
    do_functional_test('c!br', ["Kroxa, Titan of Death's Hunger", 'Fulminator Mage', 'Murderous Redcap'], ['Bosh, Iron Golem', 'Dark Ritual', 'Fires of Undeath'])

def test_multicolored_exclusive() -> None:
    do_test('c!br', '((c.id IN (SELECT card_id FROM card_color WHERE color_id = 3))) AND ((c.id IN (SELECT card_id FROM card_color WHERE color_id = 4))) AND (c.id IN (SELECT card_id FROM card_color GROUP BY card_id HAVING COUNT(card_id) <= 2))')

def test_color_identity_functional() -> None:
    yes = ['Brainstorm', 'Force of Will', 'Mystic Sanctuary', 'Venser, Shaper Savant']
    no = ['Electrolyze', 'Swamp', 'Underground Sea']
    do_functional_test('ci:u', yes, no)
    do_functional_test('cid:u', yes, no)
    do_functional_test('id:u', yes, no)

def test_color_identity() -> None:
    where = '((c.id IN (SELECT card_id FROM card_color_identity WHERE color_id = 2))) AND (c.id IN (SELECT card_id FROM card_color_identity GROUP BY card_id HAVING COUNT(card_id) <= 1))'
    do_test('ci:u', where)
    do_test('cid:u', where)
    do_test('id:u', where)
    do_test('commander:u', where)

@pytest.mark.functional
def test_color_identity_colorless_functional() -> None:
    do_functional_test('ci:c', ['Lodestone Golem', 'Wastes'], ['Academy Ruins', 'Bosh, Iron Golem', 'Lightning Bolt', 'Plains'])

def test_color_identity_colorless() -> None:
    do_test('ci:c', '(c.id NOT IN (SELECT card_id FROM card_color_identity))')

@pytest.mark.functional
def test_color_exclusively_functional() -> None:
    do_functional_test('c!r', ['Gut Shot', 'Lightning Bolt'], ['Bosh, Iron Golem', 'Lightning Helix', 'Mountain', 'Mox Ruby'])

def test_color_exclusively() -> None:
    do_test('c!r', '((c.id IN (SELECT card_id FROM card_color WHERE color_id = 4))) AND (c.id IN (SELECT card_id FROM card_color GROUP BY card_id HAVING COUNT(card_id) <= 1))')

@pytest.mark.functional
def test_color_exclusively2_functional() -> None:
    do_functional_test('c!rg', ['Assault // Battery', 'Destructive Revelry', 'Tattermunge Maniac'], ['Ancient Grudge', 'Lightning Bolt', 'Taiga'])

def test_color_exclusively2() -> None:
    do_test('c!rg', '((c.id IN (SELECT card_id FROM card_color WHERE color_id = 5))) AND ((c.id IN (SELECT card_id FROM card_color WHERE color_id = 4))) AND (c.id IN (SELECT card_id FROM card_color GROUP BY card_id HAVING COUNT(card_id) <= 2))')

def test_colorless_with_color() -> None:
    found = False
    try:
        do_test('c:cr', '')
    except InvalidValueException:
        found = True
    assert found

def test_colorless_exclusivity() -> None:
    do_test('c!c', '(c.id NOT IN (SELECT card_id FROM card_color))')

def test_colorless_exclusivity2() -> None:
    found = False
    try:
        do_test('c!cr', '')
    except InvalidValueException:
        found = True
    assert found

@pytest.mark.functional
def test_multiple_colors_functional() -> None:
    do_functional_test('c:rgw', ['Naya Charm', 'Progenitus', 'Reaper King', 'Transguild Courier'], ["Atarka's Command", 'Jegantha, the Wellspring'])

def test_multiple_colors() -> None:
    do_test('c:rgw', '((c.id IN (SELECT card_id FROM card_color WHERE color_id = 5))) AND ((c.id IN (SELECT card_id FROM card_color WHERE color_id = 4))) AND ((c.id IN (SELECT card_id FROM card_color WHERE color_id = 1)))')

def test_mana() -> None:
    do_test('mana=2WW', "(mana_cost = '{2}{W}{W}')")

def test_mana2() -> None:
    do_test('mana=X2/W2/WRB', "(mana_cost = '{X}{2/W}{2/W}{R}{B}')")

def test_mana3() -> None:
    do_test('mana=XRB', "(mana_cost = '{X}{R}{B}')")

def test_mana4() -> None:
    do_test('mana=15', "(mana_cost = '{15}')")

def test_mana5() -> None:
    do_test('mana=U/P', "(mana_cost = '{U/P}')")

def test_mana6() -> None:
    do_test('mana:c', "(mana_cost LIKE '%%{C}%%')")

def test_mana7() -> None:
    do_test('mana:uu', "(mana_cost LIKE '%%{U}{U}%%')")

def test_uppercase() -> None:
    pd_id = db().value('SELECT id FROM format WHERE name LIKE %s', ['{term}%%'.format(term='Penny Dreadful')])
    do_test('F:pd', "(c.id IN (SELECT card_id FROM card_legality WHERE format_id = {pd_id} AND legality <> 'Banned'))".format(pd_id=pd_id))

def test_subtype() -> None:
    do_test('subtype:warrior', "(c.id IN (SELECT card_id FROM card_subtype WHERE subtype LIKE '%%warrior%%'))")

def test_not() -> None:
    do_test('t:creature -t:artifact t:legendary', "(type_line LIKE '%%creature%%') AND NOT (type_line LIKE '%%artifact%%') AND (type_line LIKE '%%legendary%%')")

def test_not_cmc() -> None:
    do_test('-cmc=2', 'NOT (cmc IS NOT NULL AND cmc = 2)')

def test_cmc() -> None:
    do_test('cmc>2', '(cmc IS NOT NULL AND cmc > 2)')
    do_test('cmc=0', '(cmc IS NOT NULL AND cmc = 0)')

def test_not_text() -> None:
    do_test('o:haste -o:deathtouch o:trample NOT o:"first strike" o:lifelink', "(oracle_text LIKE '%%haste%%') AND NOT (oracle_text LIKE '%%deathtouch%%') AND (oracle_text LIKE '%%trample%%') AND NOT (oracle_text LIKE '%%first strike%%') AND (oracle_text LIKE '%%lifelink%%')")

@pytest.mark.functional
def test_color_not_text_functional() -> None:
    do_functional_test('c:b -c:r o:trample', ['Abyssal Persecutor', 'Driven // Despair'], ['Child of Alara', 'Chromanticore'])

def test_color_not_text() -> None:
    do_test('c:b -c:r o:trample', "((c.id IN (SELECT card_id FROM card_color WHERE color_id = 3))) AND NOT ((c.id IN (SELECT card_id FROM card_color WHERE color_id = 4))) AND (oracle_text LIKE '%%trample%%')")

@pytest.mark.functional
def test_color_functional() -> None:
    do_functional_test('c:g', ['Destructive Revelry', 'Rofellos, Llanowar Emissary', 'Tattermunge Maniac'], ['Ancient Grudge', 'Forest', 'Lightning Bolt'])

def test_color() -> None:
    do_test('c:g', '((c.id IN (SELECT card_id FROM card_color WHERE color_id = 5)))')

def test_or() -> None:
    do_test('a OR b', "(name LIKE '%%a%%') OR (name LIKE '%%b%%')")

def test_bad_or() -> None:
    do_test('orgg', "(name LIKE '%%orgg%%')")

def test_or_without_args() -> None:
    try:
        do_test('or GG', "(name LIKE '%%or gg%%')")
    except search.InvalidSearchException:
        pass

def test_not_without_args() -> None:
    try:
        do_test('c:r NOT', 'Expected InvalidSearchException')
    except search.InvalidSearchException:
        pass

def test_or_with_args() -> None:
    do_test('AA or GG', "(name LIKE '%%aa%%') OR (name LIKE '%%gg%%')")

def test_text() -> None:
    do_test('o:"target attacking"', "(oracle_text LIKE '%%target attacking%%')")
    do_test('fulloracle:"target attacking"', "(oracle_text LIKE '%%target attacking%%')")

def test_name() -> None:
    do_test('tension turtle', "(name LIKE '%%tension%%') AND (name LIKE '%%turtle%%')")

def test_parentheses() -> None:
    do_test('x OR (a OR (b AND c))', "(name LIKE '%%x%%') OR ((name LIKE '%%a%%') OR ((name LIKE '%%b%%') AND (name LIKE '%%c%%')))")

def test_toughness_functional() -> None:
    do_functional_test('c:r tou>2', ['Bonecrusher Giant', "Kroxa, Titan of Death's Hunger"], ['Endurance', 'Ragavan, Nimble Pilferer', 'Wurmcoil Engine'])

def test_toughness() -> None:
    do_test('c:r tou>2', '((c.id IN (SELECT card_id FROM card_color WHERE color_id = 4))) AND (toughness IS NOT NULL AND toughness > 2)')

def test_type() -> None:
    do_test('t:"human wizard"', "(type_line LIKE '%%human wizard%%')")

def test_power() -> None:
    do_test('t:wizard pow<2', "(type_line LIKE '%%wizard%%') AND (power IS NOT NULL AND power < 2)")

def test_mana_with_other() -> None:
    do_test('t:creature mana=WW o:lifelink', "(type_line LIKE '%%creature%%') AND (mana_cost = '{W}{W}') AND (oracle_text LIKE '%%lifelink%%')")

def test_mana_alone() -> None:
    do_test('mana=2uu', "(mana_cost = '{2}{U}{U}')")

def test_or_and_parentheses() -> None:
    do_test('o:"target attacking" OR (mana=2uu AND (tou>2 OR pow>2))', "(oracle_text LIKE '%%target attacking%%') OR ((mana_cost = '{2}{U}{U}') AND ((toughness IS NOT NULL AND toughness > 2) OR (power IS NOT NULL AND power > 2)))")

@pytest.mark.functional
def test_not_color_functional() -> None:
    do_functional_test('c:r -c:u', ['Lightning Bolt', 'Lightning Helix'], ['Bosh, Iron Golem', 'Electrolyze'])

def test_not_color() -> None:
    do_test('c:r -c:u', '((c.id IN (SELECT card_id FROM card_color WHERE color_id = 4))) AND NOT ((c.id IN (SELECT card_id FROM card_color WHERE color_id = 2)))')

@pytest.mark.functional
def test_complex_functional() -> None:
    do_functional_test('c:u OR (c:g tou>3)', ['Dragonlord Atarka', 'Endurance', 'Force of Negation', 'Teferi, Time Raveler', 'Venser, Shaper Savant'], ['Acidic Slime', 'Black Lotus', 'Giant Growth', 'Lightning Bolt', 'Wrenn and Six'])

def test_complex() -> None:
    do_test('c:u OR (c:g tou>3)', '((c.id IN (SELECT card_id FROM card_color WHERE color_id = 2))) OR (((c.id IN (SELECT card_id FROM card_color WHERE color_id = 5))) AND (toughness IS NOT NULL AND toughness > 3))')

def test_is_hybrid() -> None:
    do_test('is:hybrid', "((mana_cost LIKE '%%/2%%') OR (mana_cost LIKE '%%/W%%') OR (mana_cost LIKE '%%/U%%') OR (mana_cost LIKE '%%/B%%') OR (mana_cost LIKE '%%/R%%') OR (mana_cost LIKE '%%/G%%'))")

def test_is_commander() -> None:
    do_test('is:commander', "((type_line LIKE '%%legendary%%') AND ((type_line LIKE '%%creature%%') OR (oracle_text LIKE CONCAT('%%', name, ' can be your commander%%'))) AND (c.id IN (SELECT card_id FROM card_legality WHERE format_id = 4 AND legality <> 'Banned')))")

@pytest.mark.functional
def test_is_commander_illegal_commander_functional() -> None:
    do_functional_test('c:g cmc=2 is:commander', ['Ayula, Queen Among Bears', 'Gaddock Teeg'], ['Fblthp, the Lost', 'Rofellos, Llanowar Emissary'])

def test_is_spikey() -> None:
    where = search.parse(search.tokenize('is:spikey'))
    assert 'Attune with Aether' in where
    assert 'Balance' in where
    assert "name = 'Yawgmoth''s Will'" in where

def do_functional_test(query: str, yes: List[str], no: List[str]) -> None:
    results = search.search(query)
    found = [c.name for c in results]
    for name in yes:
        assert name in found
    for name in no:
        assert name not in found

def do_test(query: str, expected: str) -> None:
    where = search.parse(search.tokenize(query))
    if where != expected:
        print('\nQuery: {query}\nExpected: {expected}\n  Actual: {actual}'.format(query=query, expected=expected, actual=where))
    assert expected == where
