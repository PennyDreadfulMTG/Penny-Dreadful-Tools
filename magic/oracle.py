from typing import Dict, Iterable, List, Optional

from magic import card, fetcher, mana, multiverse, rotation
from magic.database import db
from magic.models import Card
from shared.container import Container
from shared.database import sqlescape
from shared.pd_exception import (InvalidArgumentException,
                                 InvalidDataException, TooFewItemsException)

# Primary public interface to the magic package. Call `oracle.init()` after setting up application context and before using any methods.

LEGAL_CARDS: List[str] = []
CARDS_BY_NAME: Dict[str, Card] = {}

def init(force: bool = False) -> None:
    if len(CARDS_BY_NAME) == 0 or force:
        for c in load_cards():
            CARDS_BY_NAME[c.name] = c

def valid_name(name: str) -> str:
    if name in CARDS_BY_NAME:
        return name
    canonicalized = card.canonicalize(name)
    for k in CARDS_BY_NAME:
        if canonicalized == card.canonicalize(k):
            return k
    raise InvalidDataException('Did not find any cards looking for `{name}`'.format(name=name))

def load_card(name: str) -> Card:
    return CARDS_BY_NAME.get(name, load_cards([name])[0])

def load_cards(names: Iterable[str] = None, where: Optional[str] = None) -> List[Card]:
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
    sql = multiverse.cached_base_query('({where} AND {names})'.format(where=where, names=names_clause))
    rs = db().select(sql)
    if setnames and len(setnames) != len(rs):
        missing = setnames.symmetric_difference([r['name'] for r in rs])
        raise TooFewItemsException('Expected `{namelen}` and got `{rslen}` with `{names}`.  missing=`{missing}`'.format(namelen=len(setnames), rslen=len(rs), names=setnames, missing=missing))
    return [Card(r) for r in rs]

def cards_by_name() -> Dict[str, Card]:
    return CARDS_BY_NAME

def bugged_cards() -> List[Card]:
    sql = multiverse.cached_base_query('bugs IS NOT NULL')
    rs = db().select(sql)
    return [Card(r) for r in rs]

def legal_cards(force: bool = False) -> List[str]:
    if len(LEGAL_CARDS) == 0 or force:
        db().execute('SET group_concat_max_len=100000')
        sql = 'SELECT name FROM _cache_card WHERE pd_legal'
        new_list = db().values(sql)
        LEGAL_CARDS.clear()
        for name in new_list:
            LEGAL_CARDS.append(name)
    return LEGAL_CARDS

def get_printings(generalized_card: Card) -> List[card.Printing]:
    sql = 'SELECT ' + (', '.join('p.' + property for property in card.printing_properties())) + ', s.code AS set_code' \
        + ' FROM printing AS p' \
        + ' LEFT OUTER JOIN `set` AS s ON p.set_id = s.id' \
        + ' WHERE card_id = %s '
    rs = db().select(sql, [generalized_card.id])
    return [card.Printing(r) for r in rs]

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

def scryfall_import(name: str) -> bool:
    sfcard = fetcher.internal.fetch_json('https://api.scryfall.com/cards/named?fuzzy={name}'.format(name=name))
    if sfcard['object'] == 'error':
        raise Exception()
    try:
        valid_name(sfcard['name'])
        return False
    except InvalidDataException:
        insert_scryfall_card(sfcard)
        return True

def insert_scryfall_card(sfcard: Dict, rebuild_cache: bool = True) -> None:
    imagename = '{set}_{number}'.format(set=sfcard['set'], number=sfcard['collector_number'])
    c = Container({
        'layout': sfcard['layout'],
        'cmc': int(float(sfcard['cmc'])),
        'imageName': imagename,
        'legalities': [],
        'printings': [sfcard['set']],
        'rarity': sfcard['rarity'],
        'names': []
    })
    faces = sfcard.get('card_faces', [sfcard])
    names = [face['name'] for face in faces]
    for face in faces:
        tl = face['type_line'].split('—')
        types = tl[0]
        subtypes = tl[1] if len(tl) > 1 else []

        c.update({
            'name': face['name'],
            'type': face['type_line'],
            'types': types, # This technically includes supertypes.
            'subtypes': subtypes,
            'text': face.get('oracle_text', ''),
            'manaCost': face.get('mana_cost', None)
        })
        c.names = names
        multiverse.insert_card(c)
    if rebuild_cache:
        multiverse.update_cache()
        CARDS_BY_NAME[sfcard['name']] = load_card(sfcard['name'])

def pd_rotation_changes(season_id):
    # It doesn't really make sense to do this for 'all' so just show current season in that case.
    if season_id == 'all':
        season_id = rotation.current_season_num()
    try:
        from_format_id = multiverse.get_format_id_from_season_id(int(season_id) - 1)
    except InvalidArgumentException:
        from_format_id = -1
    try:
        to_format_id = multiverse.get_format_id_from_season_id(season_id)
    except InvalidArgumentException:
        to_format_id = -1
    return changes_between_formats(from_format_id, to_format_id)

def changes_between_formats(f1, f2):
    return [query_diff_formats(f2, f1), query_diff_formats(f1, f2)]

def query_diff_formats(f1, f2):
    where = """
    c.id IN
        (SELECT card_id FROM card_legality
            WHERE format_id = {format1})
    AND c.id NOT IN
        (SELECT card_id FROM card_legality WHERE format_id = {format2})
    """.format(format1=f1, format2=f2)

    rs = db().select(multiverse.cached_base_query(where=where))
    out = [Card(r) for r in rs]
    return sorted(out, key=lambda card: card['name'])

def if_todays_prices(out=True):
    current_format = multiverse.get_format_id('Penny Dreadful')
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
        AND c.name in (SELECT name FROM prices.cache WHERE week {compare} 0.5)
        AND c.layout IN ({layouts})
    """.format(not_clause=not_clause, format=current_format, compare=compare, layouts=', '.join([sqlescape(k) for k, v in multiverse.layouts().items() if v]))

    rs = db().select(multiverse.cached_base_query(where=where))
    out = [Card(r) for r in rs]
    return sorted(out, key=lambda card: card['name'])
