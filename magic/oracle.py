from magic import card, fetcher, mana, multiverse
from magic.database import db
from magic.multiverse import base_query
from shared.database import sqlescape
from shared.pd_exception import InvalidDataException, TooFewItemsException

# 260 makes 'Odds/Ends' match 'Odds // Ends' so that's what we're using for our spellfix1 threshold default.
def search(query, fuzzy_threshold=260):
    query = card.canonicalize(query)
    sql = """
        {base_query}
        HAVING LOWER({name_query}) IN (SELECT word FROM fuzzy WHERE word MATCH ? AND distance <= {fuzzy_threshold})
            OR {name_ascii_query} LIKE ?
            OR SUM(CASE WHEN LOWER(face_name) IN (SELECT word FROM fuzzy WHERE word MATCH ? AND distance <= {fuzzy_threshold}) THEN 1 ELSE 0 END) > 0
        ORDER BY pd_legal DESC, name
    """.format(base_query=base_query(), name_query=card.name_query().format(table='u'), name_ascii_query=card.name_query('name_ascii').format(table='u'), fuzzy_threshold=fuzzy_threshold)
    fuzzy_query = '{query}*'.format(query=query)
    like_query = '%{query}%'.format(query=query)
    rs = db().execute(sql, [fuzzy_query, like_query, fuzzy_query])
    return [card.Card(r) for r in rs]

def valid_name(name):
    if name in CARDS_BY_NAME:
        return name
    else:
        try:
            cards = cards_from_query(name, 20)
            if len(cards) > 1:
                raise InvalidDataException('Found more than one card looking for `{name}`'.format(name=name))
            return cards[0].name
        except IndexError:
            raise InvalidDataException('Did not find any cards looking for `{name}`'.format(name=name))

def load_card(name):
    return load_cards([name])[0]

def load_cards(names=None):
    if names:
        names = set(names)
    if names:
        names_clause = 'HAVING LOWER({name_query}) IN ({names})'.format(name_query=card.name_query().format(table='u'), names=', '.join(sqlescape(name).lower() for name in names))
    else:
        names_clause = ''
    sql = """
        {base_query}
        {names_clause}
    """.format(base_query=base_query(), names_clause=names_clause)
    rs = db().execute(sql)
    if names and len(names) != len(rs):
        missing = names.symmetric_difference([r['name'] for r in rs])
        raise TooFewItemsException('Expected `{namelen}` and got `{rslen}` with `{names}`.  missing=`{missing}`'.format(namelen=len(names), rslen=len(rs), names=names, missing=missing))
    return [card.Card(r) for r in rs]

def bugged_cards():
    sql = base_query() + "HAVING bug_desc NOT NULL"
    rs = db().execute(sql)
    return [card.Card(r) for r in rs]

def legal_cards(force=False):
    if len(LEGAL_CARDS) == 0 or force:
        new_list = multiverse.set_legal_cards(force)
        if new_list is None:
            sql = 'SELECT name FROM ({base_query}) WHERE id IN (SELECT card_id FROM card_legality WHERE format_id = {format_id})'.format(base_query=base_query(), format_id=multiverse.get_format_id('Penny Dreadful'))
            new_list = [row['name'] for row in db().execute(sql)]
        LEGAL_CARDS.clear()
        for name in new_list:
            LEGAL_CARDS.append(name)
    return LEGAL_CARDS

def get_printings(generalized_card: card.Card):
    sql = 'SELECT ' + (', '.join('p.' + property for property in card.printing_properties())) + ', s.code AS set_code' \
        + ' FROM printing AS p' \
        + ' OUTER LEFT JOIN `set` AS s ON p.set_id = s.id' \
        + ' WHERE card_id = ? '
    rs = db().execute(sql, [generalized_card.id])
    return [card.Printing(r) for r in rs]

def deck_sort(c):
    s = ''
    if c.is_creature():
        s += 'A'
    elif c.is_land():
        s += 'C'
    else:
        s += 'B'
    m = 'A'
    for cost in c.get('mana_cost') or ():
        if mana.has_x(cost):
            m = 'X'
    s += m
    s += str(c.cmc).zfill(10)
    s += c.name
    return s

def cards_from_query(query, fuzziness_threshold=260):
    # Skip searching if the request is too short.
    if len(query) <= 2:
        return []

    query = card.canonicalize(query)

    # If we searched for an alias, change query so we can find the card in the results.
    for alias, name in fetcher.card_aliases():
        if query == card.canonicalize(alias):
            query = card.canonicalize(name)

    cards = search(query, fuzziness_threshold)
    cards = [c for c in cards if c.layout != 'token' and c.type != 'Vanguard']

    # First look for an exact match.
    results = []
    for c in cards:
        if query == card.canonicalize(c.name):
            results.append(c)
    if len(results) > 0:
        return results

    for c in cards:
        names = [card.canonicalize(name) for name in c.names]
        if query in names:
            results.append(c)
    if len(results) > 0:
        return results


    # If not found, use cards that start with the query and a punctuation char.
    for c in cards:
        names = [card.canonicalize(name) for name in c.names]
        for name in names:
            if name.startswith('{query} '.format(query=query)) or name.startswith('{query},'.format(query=query)):
                results.append(c)
    if len(results) > 0:
        return results

    # If not found, use cards that start with the query.
    for c in cards:
        names = [card.canonicalize(name) for name in c.names]
        for name in names:
            if name.startswith(query):
                results.append(c)
    if len(results) > 0:
        return results

    # If we didn't find any of those then use all search results.
    return cards

LEGAL_CARDS = []
multiverse.init()
CARDS_BY_NAME = {c.name: c for c in load_cards()}
