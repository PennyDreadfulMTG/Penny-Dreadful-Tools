from collections.abc import Iterable, Sequence

from magic import card, layout, mana, multiverse, seasons, whoosh_write
from magic.abc import CardDescription
from magic.database import db
from magic.models import Card, Printing
from shared import configuration, fetch_tools, guarantee
from shared.container import Container
from shared.database import sqlescape, sqllikeescape
from shared.pd_exception import InvalidArgumentException, InvalidDataException, TooFewItemsException

# Primary public interface to the magic package. Call `oracle.init()` after setting up application context and before using any methods.

LEGAL_CARDS: list[str] = []
CARDS_BY_NAME: dict[str, Card] = {}

def init(force: bool = False) -> None:
    if len(CARDS_BY_NAME) == 0 or force:
        for c in load_cards():
            CARDS_BY_NAME[c.name] = c
        for c in load_cards_with_flavor_names():
            for fn in c.flavor_names.split('|'):
                CARDS_BY_NAME[fn] = c

def valid_name(name: str) -> str:
    if name in CARDS_BY_NAME:
        return CARDS_BY_NAME[name].name
    try:
        front = name[0:name.index('/')].strip()
    except ValueError:
        front = name
    if front in CARDS_BY_NAME:
        return front
    canonicalized_name = card.canonicalize(name)
    canonicalized_front = card.canonicalize(front)
    for k in CARDS_BY_NAME:
        canonicalized = card.canonicalize(k)
        if canonicalized_name == canonicalized or canonicalized_front == canonicalized:
            return k
    raise InvalidDataException(f'Did not find any cards looking for `{name}`')

def load_card(name: str) -> Card:
    return CARDS_BY_NAME.get(name) or load_cards([name])[0]

def load_cards(names: Iterable[str] | None = None, where: str | None = None) -> list[Card]:
    if names == []:
        return []
    if names:
        setnames = set(names)
    else:
        setnames = set()
    if setnames:
        names_clause = 'c.name IN ({names})'.format(names=', '.join(sqlescape(name) for name in setnames))
    else:
        names_clause = '(1 = 1)'
    if where is None:
        where = '(1 = 1)'
    sql = multiverse.cached_base_query(f'({where} AND {names_clause})')
    rs = db().select(sql)
    if setnames and len(setnames) != len(rs):
        missing = setnames.symmetric_difference([r['name'] for r in rs])
        raise TooFewItemsException(f'Expected `{len(setnames)}` and got `{len(rs)}` with `{setnames}`.  missing=`{missing}`')
    return [Card(r) for r in rs]

def cards_by_name() -> dict[str, Card]:
    return CARDS_BY_NAME

def load_cards_with_flavor_names() -> list[Card]:
    sql = multiverse.cached_base_query('c.flavor_names IS NOT NULL')
    rs = db().select(sql)
    return [Card(r) for r in rs]

def bugged_cards() -> list[Card]:
    sql = multiverse.cached_base_query('bugs IS NOT NULL')
    rs = db().select(sql)
    return [Card(r) for r in rs]

def legal_cards(force: bool = False) -> list[str]:
    if len(LEGAL_CARDS) == 0 or force:
        db().execute('SET group_concat_max_len=100000')
        sql = 'SELECT name FROM _cache_card WHERE pd_legal'
        new_list = db().values(sql)
        LEGAL_CARDS.clear()
        for name in new_list:
            LEGAL_CARDS.append(name)
    return LEGAL_CARDS

def get_printings(generalized_card: Card) -> list[Printing]:
    sql = 'SELECT ' + (', '.join('p.' + property for property in card.printing_properties())) + ', s.code AS set_code, s.name AS set_name ' \
        + ' FROM printing AS p' \
        + ' LEFT OUTER JOIN `set` AS s ON p.set_id = s.id' \
        + ' WHERE card_id = %s '
    rs = db().select(sql, [generalized_card.id])
    return [Printing(r) for r in rs]

def get_printing(generalized_card: Card, setcode: str) -> Printing | None:
    if setcode is None:
        return None
    sql = 'SELECT ' + (', '.join('p.' + property for property in card.printing_properties())) + ', s.code AS set_code' \
        + ' FROM printing AS p' \
        + ' LEFT OUTER JOIN `set` AS s ON p.set_id = s.id' \
        + f' WHERE card_id = %s AND (s.code = %s OR s.name LIKE {sqllikeescape(setcode)})' \
        + ' ORDER BY s.code = %s DESC, s.released_at' \
        + ' LIMIT 1'
    rs = db().select(sql, [generalized_card.id, setcode, setcode])
    if not rs:
        return None
    return Printing(rs[0])

def get_set(set_id: int) -> Container:
    rs = db().select('SELECT ' + (', '.join(property for property in card.set_properties())) + ' FROM `set` WHERE id = %s', [set_id])
    return guarantee.exactly_one([Container(r) for r in rs])

def deck_sort(c: Card) -> str:
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

async def scryfall_import_async(name: str) -> bool:
    sfcard = await fetch_tools.fetch_json_async(f'https://api.scryfall.com/cards/named?fuzzy={name}')
    if sfcard['object'] == 'error':
        raise Exception
    try:
        valid_name(sfcard['name'])
        print(f"Not adding {sfcard['name']} to the database as we already have it.")
        return False
    except InvalidDataException:
        print(f"Adding {sfcard['name']} to the database as we don't have it.")
        await add_cards_and_update_async([sfcard])
        return True

def pd_rotation_changes(season_id: int) -> tuple[Sequence[Card], Sequence[Card]]:
    # It doesn't really make sense to do this for 'all' so just show current season in that case.
    if season_id == 0:
        season_id = seasons.current_season_num()
    try:
        from_format_id = multiverse.get_format_id_from_season_id(int(season_id) - 1)
    except InvalidArgumentException:
        from_format_id = -1
    try:
        to_format_id = multiverse.get_format_id_from_season_id(season_id)
    except InvalidArgumentException:
        to_format_id = -1
    return changes_between_formats(from_format_id, to_format_id)


def changes_between_formats(f1: int, f2: int) -> tuple[Sequence[Card], Sequence[Card]]:
    return (query_diff_formats(f2, f1), query_diff_formats(f1, f2))

def query_diff_formats(f1: int, f2: int) -> Sequence[Card]:
    where = f"""
    c.id IN
        (SELECT card_id FROM card_legality
            WHERE format_id = {f1})
    AND c.id NOT IN
        (SELECT card_id FROM card_legality WHERE format_id = {f2})
    """

    rs = db().select(multiverse.cached_base_query(where=where))
    out = [Card(r) for r in rs]
    return sorted(out, key=lambda card: card['name'])

def if_todays_prices(out: bool = True) -> list[Card]:
    current_format = multiverse.get_format_id(f'Penny Dreadful {seasons.current_season_code()}')
    if out:
        not_clause = ''
        compare = '<'
    else:
        not_clause = 'NOT'
        compare = '>='

    where = """
        c.id {not_clause} IN
            (SELECT card_id FROM card_legality
                WHERE format_id = {format})
        AND c.name in (SELECT name FROM `{prices_database}`.cache WHERE week {compare} 0.5)
        AND c.layout IN ({layouts})
    """.format(not_clause=not_clause, format=current_format, prices_database=configuration.get('prices_database'),
               compare=compare, layouts=', '.join([sqlescape(lo) for lo in layout.playable_layouts()]))

    rs = db().select(multiverse.cached_base_query(where=where))
    cards = [Card(r) for r in rs]
    return sorted(cards, key=lambda card: card['name'])

async def add_cards_and_update_async(printings: list[CardDescription]) -> None:
    if not printings:
        return
    ids = await multiverse.insert_cards_async(printings)
    multiverse.add_to_cache(ids)
    cs = [Card(r) for r in db().select(multiverse.cached_base_query('c.id IN (' + ','.join([str(id) for id in ids]) + ')'))]
    whoosh_write.reindex_specific_cards(cs)
    for c in cs:
        CARDS_BY_NAME[c.name] = c
