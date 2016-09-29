from find import search

# Run these tests from the project root with python3 -m "find.tests" find/tests.py

def tests():
    assert search.Key.match(['c'])
    assert search.Key.match(['mana'])
    assert not search.Key.match(['z'])
    assert not search.Key.match(['magic'])
    assert not search.Key.match([''])
    assert not search.Key.match([' '])
    assert search.Criterion.match(['t', 'o', 'u', '>', '2'])

    do_test('subtype:warrior', "(id IN (SELECT card_id FROM card_subtype WHERE subtype LIKE '%warrior%'))")
    do_test('t:creature -t:artifact t:legendary', "(type LIKE '%creature%') AND NOT (type LIKE '%artifact%') AND (type LIKE '%legendary%')")
    do_test('-cmc=2', "NOT (cmc IS NOT NULL AND cmc <> '' AND CAST(cmc AS REAL) = 2)")
    do_test('cmc>2', "(cmc IS NOT NULL AND cmc <> '' AND CAST(cmc AS REAL) > 2)")
    do_test('o:haste NOT o:deathtouch o:trample NOT o:"first strike" o:lifelink', "(text LIKE '%haste%') AND NOT (text LIKE '%deathtouch%') AND (text LIKE '%trample%') AND NOT (text LIKE '%first strike%') AND (text LIKE '%lifelink%')")
    do_test('c:b NOT c:r o:trample', "(id IN (SELECT card_id FROM card_color WHERE color_id = 3)) AND NOT (id IN (SELECT card_id FROM card_color WHERE color_id = 4)) AND (text LIKE '%trample%')")
    do_test('c:g', '(id IN (SELECT card_id FROM card_color WHERE color_id = 5))')
    do_test("a OR b", "(name LIKE '%a%' OR type LIKE '%a%' OR text LIKE '%a%') OR (name LIKE '%b%' OR type LIKE '%b%' OR text LIKE '%b%')")
    do_test('o:"target attacking"', "(text LIKE '%target attacking%')")
    do_test('tension turtle', "(name LIKE '%tension%' OR type LIKE '%tension%' OR text LIKE '%tension%') AND (name LIKE '%turtle%' OR type LIKE '%turtle%' OR text LIKE '%turtle%')")
    do_test('x OR (a OR (b AND c))', "(name LIKE '%x%' OR type LIKE '%x%' OR text LIKE '%x%') OR ((name LIKE '%a%' OR type LIKE '%a%' OR text LIKE '%a%') OR ((name LIKE '%b%' OR type LIKE '%b%' OR text LIKE '%b%') AND (name LIKE '%c%' OR type LIKE '%c%' OR text LIKE '%c%')))")
    do_test('c:r tou>2', "(id IN (SELECT card_id FROM card_color WHERE color_id = 4)) AND (toughness IS NOT NULL AND toughness <> '' AND CAST(toughness AS REAL) > 2)")
    do_test('t:"human wizard"', "(type LIKE '%human wizard%')")
    do_test('t:wizard pow<2', "(type LIKE '%wizard%') AND (power IS NOT NULL AND power <> '' AND CAST(power AS REAL) < 2)")
    do_test('t:creature mana=WW o:lifelink', "(type LIKE '%creature%') AND (cost LIKE 'WW') AND (text LIKE '%lifelink%')")
    do_test('mana=2uu', "(cost LIKE '2uu')")
    do_test('o:"target attacking" OR (mana=2uu AND (tou>2 OR pow>2))', "(text LIKE '%target attacking%') OR ((cost LIKE '2uu') AND ((toughness IS NOT NULL AND toughness <> '' AND CAST(toughness AS REAL) > 2) OR (power IS NOT NULL AND power <> '' AND CAST(power AS REAL) > 2)))")
    do_test('c:r NOT c:u', "(id IN (SELECT card_id FROM card_color WHERE color_id = 4)) AND NOT (id IN (SELECT card_id FROM card_color WHERE color_id = 2))")
    do_test('c:u OR (c:g AND NOT tou>3)', "(id IN (SELECT card_id FROM card_color WHERE color_id = 2)) OR ((id IN (SELECT card_id FROM card_color WHERE color_id = 5)) AND NOT (toughness IS NOT NULL AND toughness <> '' AND CAST(toughness AS REAL) > 3))")
    print()

def do_test(query, expected):
    where_clause = search.parse(search.tokenize(query))
    if where_clause != expected:
        print("\nQuery: {query}\nExpected: {expected}\n  Actual: {actual}".format(query=query, expected=expected, actual=where_clause))
    else:
        print('.', end="")

tests()
