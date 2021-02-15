from find import search
from magic.database import db


def test_match():
    assert search.Key.match(['c'])
    assert search.Key.match(['mana'])
    assert not search.Key.match(['z'])
    assert not search.Key.match([''])
    assert not search.Key.match([' '])
    assert not search.Criterion.match(list('magic:2uu'))
    assert search.Criterion.match(list('tou>2'))

def test_edition():
    do_test('e:ktk', "(c.id IN (SELECT card_id FROM printing WHERE set_id IN (SELECT id FROM `set` WHERE name LIKE '%%ktk%%' OR code = 'ktk')))")

def test_special_chars():
    do_test('o:a_c%', "(oracle_text LIKE '%%a\\_c\\%%%%')")

def test_tilde():
    expected = "(oracle_text LIKE CONCAT('%%sacrifice ', name, '%%'))"
    do_test('o:"sacrifice ~"', expected)

def test_double_tilde():
    expected = "(oracle_text LIKE CONCAT('%%sacrifice ', name, ': ', name, ' deals 2 damage to target creature%%'))"
    do_test('o:"sacrifice ~: ~ deals 2 damage to target creature"', expected)

def test_only_multicolored():
    do_test('c:m', '((1 = 1) AND (c.id IN (SELECT card_id FROM card_color GROUP BY card_id HAVING COUNT(card_id) > 1)))')

def test_multicolored():
    do_test('c:bm', '((c.id IN (SELECT card_id FROM card_color WHERE color_id = 3)) AND (c.id IN (SELECT card_id FROM card_color GROUP BY card_id HAVING COUNT(card_id) > 1)))')

def test_multicolored_coloridentity():
    do_test('ci:bm', '(((c.id IN (SELECT card_id FROM card_color_identity WHERE color_id = 3)) AND (c.id NOT IN (SELECT card_id FROM card_color_identity WHERE color_id <> 3))) AND (c.id IN (SELECT card_id FROM card_color_identity GROUP BY card_id HAVING COUNT(card_id) > 1)))')

def test_exclusivemulitcolored_same():
    do_test('ci!bm', '(((c.id IN (SELECT card_id FROM card_color_identity WHERE color_id = 3)) AND (c.id NOT IN (SELECT card_id FROM card_color_identity WHERE color_id <> 3))) AND (c.id IN (SELECT card_id FROM card_color_identity GROUP BY card_id HAVING COUNT(card_id) > 1)))')

def test_mulitcolored_multiple():
    do_test('c:brm', "(((c.id IN (SELECT card_id FROM card_color WHERE color_id = 3)) OR (c.id IN (SELECT card_id FROM card_color WHERE color_id = 4))) AND (c.id IN (SELECT card_id FROM card_color GROUP BY card_id HAVING COUNT(card_id) > 1)))")

def test_multicolored_exclusive():
    do_test('c!brm', "((((c.id IN (SELECT card_id FROM card_color WHERE color_id = 3)) OR (c.id IN (SELECT card_id FROM card_color WHERE color_id = 4))) AND (c.id NOT IN (SELECT card_id FROM card_color WHERE color_id <> 3 AND color_id <> 4))) AND (c.id IN (SELECT card_id FROM card_color GROUP BY card_id HAVING COUNT(card_id) > 1)))")

def test_color_identity():
    do_test('ci:u', '((c.id IN (SELECT card_id FROM card_color_identity WHERE color_id = 2)) AND (c.id NOT IN (SELECT card_id FROM card_color_identity WHERE color_id <> 2)))')

def test_color_identity_colorless():
    do_test('ci:c', '(c.id NOT IN (SELECT card_id FROM card_color_identity))')

def test_color_exclusively():
    do_test('c!r', '((c.id IN (SELECT card_id FROM card_color WHERE color_id = 4)) AND (c.id NOT IN (SELECT card_id FROM card_color WHERE color_id <> 4)))')

def test_color_exclusively2():
    do_test('c!rg', '(((c.id IN (SELECT card_id FROM card_color WHERE color_id = 4)) OR (c.id IN (SELECT card_id FROM card_color WHERE color_id = 5))) AND (c.id NOT IN (SELECT card_id FROM card_color WHERE color_id <> 4 AND color_id <> 5)))')

def test_colorless_exclusivity():
    do_test('c!c', '(c.id NOT IN (SELECT card_id FROM card_color))')

def test_colorless_exclusivity2():
    do_test('c!cr', '(((c.id NOT IN (SELECT card_id FROM card_color)) OR (c.id IN (SELECT card_id FROM card_color WHERE color_id = 4))) AND (c.id NOT IN (SELECT card_id FROM card_color WHERE color_id <> 4)))')

def test_multiple_colors():
    do_test('c:rgw', "((c.id IN (SELECT card_id FROM card_color WHERE color_id = 4)) OR (c.id IN (SELECT card_id FROM card_color WHERE color_id = 5)) OR (c.id IN (SELECT card_id FROM card_color WHERE color_id = 1)))")

def test_mana():
    do_test('mana=2WW', "(mana_cost = '{2}{W}{W}')")

def test_mana2():
    do_test('mana=X2/W2/WRB', "(mana_cost = '{X}{2/W}{2/W}{R}{B}')")

def test_mana3():
    do_test('mana=XRB', "(mana_cost = '{X}{R}{B}')")

def test_mana4():
    do_test('mana=15', "(mana_cost = '{15}')")

def test_mana5():
    do_test('mana=U/P', "(mana_cost = '{U/P}')")

def test_mana6():
    do_test('mana:c', "(mana_cost LIKE '%%{C}%%')")

def test_mana7():
    do_test('mana:uu', "(mana_cost LIKE '%%{U}{U}%%')")

def test_uppercase():
    pd_id = db().value('SELECT id FROM format WHERE name LIKE %s', ['{term}%%'.format(term='Penny Dreadful')])
    do_test('F:pd', "(c.id IN (SELECT card_id FROM card_legality WHERE format_id = {pd_id} AND legality <> 'Banned'))".format(pd_id=pd_id))

def test_subtype():
    do_test('subtype:warrior', "(c.id IN (SELECT card_id FROM card_subtype WHERE subtype LIKE '%%warrior%%'))")

def test_not():
    do_test('t:creature -t:artifact t:legendary', "(type LIKE '%%creature%%') AND NOT (type LIKE '%%artifact%%') AND (type LIKE '%%legendary%%')")

def test_not_cmc():
    do_test('-cmc=2', "NOT (cmc IS NOT NULL AND cmc <> '' AND cmc = 2)")

def test_cmc():
    do_test('cmc>2', "(cmc IS NOT NULL AND cmc <> '' AND cmc > 2)")

def test_not_text():
    do_test('o:haste NOT o:deathtouch o:trample NOT o:"first strike" o:lifelink', "(oracle_text LIKE '%%haste%%') AND NOT (oracle_text LIKE '%%deathtouch%%') AND (oracle_text LIKE '%%trample%%') AND NOT (oracle_text LIKE '%%first strike%%') AND (oracle_text LIKE '%%lifelink%%')")

def test_color_not_text():
    do_test('c:b NOT c:r o:trample', "(c.id IN (SELECT card_id FROM card_color WHERE color_id = 3)) AND NOT (c.id IN (SELECT card_id FROM card_color WHERE color_id = 4)) AND (oracle_text LIKE '%%trample%%')")

def test_color():
    do_test('c:g', '(c.id IN (SELECT card_id FROM card_color WHERE color_id = 5))')

def test_or():
    do_test('a OR b', "(name LIKE '%%a%%') OR (name LIKE '%%b%%')")

def test_bad_or():
    do_test('orgg', "(name LIKE '%%orgg%%')")

def test_or_without_args():
    try:
        do_test('or GG', "(name LIKE '%%or gg%%')")
    except search.InvalidSearchException:
        pass

def test_not_without_args():
    try:
        do_test('c:r NOT', 'Expected InvalidSearchException')
    except search.InvalidSearchException:
        pass

def test_or_with_args():
    do_test('AA or GG', "(name LIKE '%%aa%%') OR (name LIKE '%%gg%%')")

def test_text():
    do_test('o:"target attacking"', "(oracle_text LIKE '%%target attacking%%')")

def test_name():
    do_test('tension turtle', "(name LIKE '%%tension%%') AND (name LIKE '%%turtle%%')")

def test_parentheses():
    do_test('x OR (a OR (b AND c))', "(name LIKE '%%x%%') OR ((name LIKE '%%a%%') OR ((name LIKE '%%b%%') AND (name LIKE '%%c%%')))")

def test_toughness():
    do_test('c:r tou>2', "(c.id IN (SELECT card_id FROM card_color WHERE color_id = 4)) AND (toughness IS NOT NULL AND toughness <> '' AND toughness > 2)")

def test_type():
    do_test('t:"human wizard"', "(type LIKE '%%human wizard%%')")

def test_power():
    do_test('t:wizard pow<2', "(type LIKE '%%wizard%%') AND (power IS NOT NULL AND power <> '' AND power < 2)")

def test_mana_with_other():
    do_test('t:creature mana=WW o:lifelink', "(type LIKE '%%creature%%') AND (mana_cost = '{W}{W}') AND (oracle_text LIKE '%%lifelink%%')")

def test_mana_alone():
    do_test('mana=2uu', "(mana_cost = '{2}{U}{U}')")

def test_or_and_parentheses():
    do_test('o:"target attacking" OR (mana=2uu AND (tou>2 OR pow>2))', "(oracle_text LIKE '%%target attacking%%') OR ((mana_cost = '{2}{U}{U}') AND ((toughness IS NOT NULL AND toughness <> '' AND toughness > 2) OR (power IS NOT NULL AND power <> '' AND power > 2)))")

def test_not_color():
    do_test('c:r NOT c:u', '(c.id IN (SELECT card_id FROM card_color WHERE color_id = 4)) AND NOT (c.id IN (SELECT card_id FROM card_color WHERE color_id = 2))')

def test_complex():
    do_test('c:u OR (c:g AND NOT tou>3)', "(c.id IN (SELECT card_id FROM card_color WHERE color_id = 2)) OR ((c.id IN (SELECT card_id FROM card_color WHERE color_id = 5)) AND NOT (toughness IS NOT NULL AND toughness <> '' AND toughness > 3))")

def test_is_hybrid():
    do_test('is:hybrid', "((mana_cost LIKE '%%/2%%') OR (mana_cost LIKE '%%/W%%') OR (mana_cost LIKE '%%/U%%') OR (mana_cost LIKE '%%/B%%') OR (mana_cost LIKE '%%/R%%') OR (mana_cost LIKE '%%/G%%'))")

def do_test(query, expected):
    where = search.parse(search.tokenize(query))
    assert where == expected or print('\nQuery: {query}\nExpected: {expected}\n  Actual: {actual}'.format(query=query, expected=expected, actual=where))
