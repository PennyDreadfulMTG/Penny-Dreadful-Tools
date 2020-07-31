import copy
import re
import unicodedata
from typing import Dict, List, Optional, Tuple

from mypy_extensions import TypedDict

# Properties of the various aspects of cards with information about how to store and retrieve them from the database.
ColumnDescription = TypedDict('ColumnDescription', {
    'type': str,
    'nullable': bool,
    'primary_key': bool,
    'query': str,
    'scryfall': bool,
    'foreign_key': Optional[Tuple[str, str]],
    'default': Optional[str],
    'unique': bool,
    'unique_with': Optional[List[str]],
    })
TableDescription = Dict[str, ColumnDescription]

MAX_LEN_TEXT = 21845
MAX_LEN_VARCHAR = 190

BOOLEAN = 'BOOLEAN'
DATE = 'INTEGER'
INTEGER = 'INTEGER'
REAL = 'REAL'
TEXT = 'LONGTEXT'
VARCHAR = 'VARCHAR({n})'.format(n=MAX_LEN_VARCHAR)

BASE: ColumnDescription = {
    'type': VARCHAR,
    'nullable': True,
    'primary_key': False,
    'query': '`{table}`.`{column}` AS `{column}`',
    'scryfall': True,
    'foreign_key': None,
    'default': None,
    'unique': False,
    'unique_with': None
}

def base_query_properties() -> TableDescription:
    # Important that these are in this order so that 'id' from card overwrites 'id' from face.
    props = face_properties()
    props.update(card_properties())
    props.update(base_query_specific_properties())
    return props

def base_query_lite_properties() -> TableDescription:
    # Important that these are in this order so that 'id' from card overwrites 'id' from face.
    props = face_properties()
    props.update(card_properties())
    props['names'] = copy.deepcopy(BASE)
    props['names']['type'] = TEXT
    props['names']['query'] = "GROUP_CONCAT(face_name SEPARATOR '|') AS names"
    return props

def base_query_specific_properties() -> TableDescription:
    props = {}
    for k in ['legalities', 'names', 'pd_legal', 'bugs']:
        props[k] = copy.deepcopy(BASE)
    props['names']['type'] = TEXT
    props['names']['query'] = "GROUP_CONCAT(face_name SEPARATOR '|') AS names"
    props['legalities']['type'] = TEXT
    props['legalities']['query'] = 'legalities'
    props['pd_legal']['type'] = BOOLEAN
    props['bugs']['query'] = 'pd_legal'
    props['bugs']['type'] = TEXT
    props['bugs']['query'] = 'bugs'
    return props

def card_properties() -> TableDescription:
    props = {}
    for k in ['id', 'layout']:
        props[k] = copy.deepcopy(BASE)
    props['id']['type'] = INTEGER
    props['id']['nullable'] = False
    props['id']['primary_key'] = True
    props['id']['scryfall'] = False
    props['layout']['nullable'] = False
    return props

def face_properties() -> TableDescription:
    props = {}
    base = copy.deepcopy(BASE)
    base['query'] = "GROUP_CONCAT(CASE WHEN `{table}`.position = 1 THEN `{table}`.`{column}` ELSE '' END SEPARATOR '') AS `{column}`"
    for k in ['id', 'name', 'mana_cost', 'cmc', 'power', 'toughness', 'power', 'toughness', 'loyalty', 'type_line', 'oracle_text', 'hand', 'life', 'position', 'card_id']:
        props[k] = copy.deepcopy(base)
    for k in ['id', 'position', 'card_id']:
        props[k]['scryfall'] = False
    for k in ['id', 'name', 'position', 'type_line', 'oracle_text', 'card_id']:
        props[k]['nullable'] = False
    for k in ['id', 'card_id', 'hand', 'life']:
        props[k]['type'] = INTEGER
        props[k]['query'] = 'SUM(CASE WHEN `{table}`.position = 1 THEN `{table}`.`{column}` ELSE 0 END) AS `{column}`'
    props['id']['primary_key'] = True
    props['id']['query'] = '`{table}`.`{column}` AS face_id'
    props['cmc']['type'] = REAL
    props['name']['query'] = """{name_query} AS name""".format(name_query=name_query())
    props['cmc']['query'] = """{cmc_query} AS cmc""".format(cmc_query=cmc_query())
    props['mana_cost']['query'] = """{mana_cost_query} AS mana_cost""".format(mana_cost_query=mana_cost_query())
    props['type_line']['query'] = """{type_query} AS type_line""".format(type_query=type_query())
    for k in ['oracle_text']:
        props[k]['query'] = "GROUP_CONCAT(`{table}`.`{column}` SEPARATOR '\n-----\n') AS `{column}`"
        props[k]['type'] = TEXT
    props['card_id']['foreign_key'] = ('card', 'id')
    return props

def set_properties() -> TableDescription:
    props = {}
    for k in ['id', 'name', 'code', 'uri', 'scryfall_uri', 'search_uri', 'released_at', 'set_type', 'card_count', 'parent_set_code', 'digital', 'foil_only', 'icon_svg_uri']:
        props[k] = copy.deepcopy(BASE)
    for k in ['id', 'name', 'code', 'released_at']:
        props[k]['nullable'] = False
    props['id']['primary_key'] = True
    props['id']['type'] = INTEGER
    props['id']['scryfall'] = False
    props['released_at']['type'] = DATE
    props['digital']['type'] = BOOLEAN
    props['name']['unique'] = True
    props['code']['unique'] = True
    props['uri']['unique'] = True
    props['scryfall_uri']['unique'] = True
    return props

def printing_properties() -> TableDescription:
    props = {}
    for k in ['id', 'system_id', 'flavor', 'artist', 'number', 'watermark', 'reserved', 'card_id', 'set_id', 'rarity_id']:
        props[k] = copy.deepcopy(BASE)
    for k in ['id', 'system_id', 'artist', 'card_id', 'set_id']:
        props[k]['nullable'] = False
    for k in ['id', 'card_id', 'set_id', 'rarity_id']:
        props[k]['type'] = INTEGER
        props[k]['scryfall'] = False
    props['id']['primary_key'] = True
    props['id']['nullable'] = False
    props['reserved']['type'] = BOOLEAN
    props['card_id']['foreign_key'] = ('card', 'id')
    props['set_id']['foreign_key'] = ('set', 'id')
    props['rarity_id']['foreign_key'] = ('rarity', 'id')
    props['flavor']['type'] = TEXT
    return props

def color_properties() -> TableDescription:
    props = {}
    for k in ['id', 'name', 'symbol']:
        props[k] = copy.deepcopy(BASE)
        props[k]['nullable'] = False
    props['id']['type'] = INTEGER
    props['id']['primary_key'] = True
    return props

def card_color_properties() -> TableDescription:
    props = {}
    for k in ['id', 'card_id', 'color_id']:
        props[k] = copy.deepcopy(BASE)
        props[k]['type'] = INTEGER
        props[k]['nullable'] = False
        props[k]['scryfall'] = False
    props['id']['primary_key'] = True
    props['card_id']['foreign_key'] = ('card', 'id')
    props['card_id']['unique_with'] = ['color_id']
    props['color_id']['foreign_key'] = ('color', 'id')
    return props

def card_type_properties(typetype: str) -> TableDescription:
    props = {}
    for k in ['id', 'card_id', typetype]:
        props[k] = copy.deepcopy(BASE)
        props[k]['nullable'] = False
    props['id']['type'] = INTEGER
    props['id']['primary_key'] = True
    props['card_id']['type'] = INTEGER
    props['card_id']['foreign_key'] = ('card', 'id')
    props['card_id']['unique_with'] = [typetype]
    return props

def format_properties() -> TableDescription:
    props = {}
    for k in ['id', 'name']:
        props[k] = copy.deepcopy(BASE)
        props[k]['nullable'] = False
    props['id']['type'] = INTEGER
    props['id']['primary_key'] = True
    props['name']['unique'] = True
    return props

def card_legality_properties() -> TableDescription:
    props = {}
    for k in ['id', 'card_id', 'format_id', 'legality']:
        props[k] = copy.deepcopy(BASE)
        props[k]['nullable'] = False
        props[k]['scryfall'] = False
    props['id']['type'] = INTEGER
    props['id']['primary_key'] = True
    props['card_id']['type'] = INTEGER
    props['card_id']['foreign_key'] = ('card', 'id')
    props['card_id']['unique_with'] = ['format_id']
    props['format_id']['type'] = INTEGER
    props['format_id']['foreign_key'] = ('format', 'id')
    props['legality']['nullable'] = True
    return props

def card_alias_properties() -> TableDescription:
    props = {}
    for k in ['id', 'card_id', 'alias']:
        props[k] = copy.deepcopy(BASE)
        props[k]['nullable'] = False
    props['id']['type'] = INTEGER
    props['id']['primary_key'] = True
    props['card_id']['type'] = INTEGER
    props['card_id']['foreign_key'] = ('card', 'id')
    props['card_id']['unique_with'] = ['alias']
    return props

def card_bug_properties() -> TableDescription:
    props = {}
    for k in ['id', 'card_id', 'description', 'classification', 'last_confirmed', 'url', 'from_bug_blog', 'bannable']:
        props[k] = copy.deepcopy(BASE)
        props[k]['nullable'] = False
    props['id']['type'] = INTEGER
    props['id']['primary_key'] = True
    props['card_id']['type'] = INTEGER
    props['card_id']['foreign_key'] = ('card', 'id')
    props['description']['type'] = TEXT
    props['last_confirmed']['type'] = INTEGER
    props['url']['type'] = TEXT
    props['from_bug_blog']['type'] = BOOLEAN
    props['bannable']['type'] = BOOLEAN
    return props

def name_query(column: str = 'face_name') -> str:
    return """
        CASE
        WHEN layout = 'transform' OR layout = 'flip' OR layout = 'meld' OR layout = 'adventure' THEN
            GROUP_CONCAT(CASE WHEN `{table}`.position = 1 THEN {column} ELSE '' END SEPARATOR '')
        ELSE
            GROUP_CONCAT({column} SEPARATOR ' // ' )
        END
    """.format(column=column, table='{table}')

def cmc_query() -> str:
    return """
        CASE
        WHEN layout = 'split' THEN
            SUM(CASE WHEN `{table}`.cmc IS NOT NULL THEN `{table}`.cmc ELSE 0 END)
        ELSE
            SUM(CASE WHEN `{table}`.position = 1 THEN `{table}`.cmc ELSE 0 END)
        END
    """

def mana_cost_query() -> str:
    return """
        CASE
        WHEN layout = 'flip' THEN
            GROUP_CONCAT(CASE WHEN `{table}`.position = 1 THEN {column} ELSE '' END SEPARATOR '')
        ELSE
            GROUP_CONCAT(`{table}`.`{column}` SEPARATOR '|')
        END
    """

def type_query() -> str:
    return """
        GROUP_CONCAT(CASE WHEN `{table}`.position = 1 THEN {column} ELSE '' END SEPARATOR '')
    """

def unaccent(s: str) -> str:
    return ''.join((c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn'))

def canonicalize(name: str) -> str:
    if name.find('/') >= 0 and name.find('//') == -1:
        name = name.replace('/', '//')
    if name.find('//') >= 0 and name.find(' // ') == -1:
        name = name.replace('//', ' // ')
    name = re.sub(r' \([ab]\)$', '', name)
    # Replace ligature and smart quotes.
    name = name.replace('Æ', 'Ae').replace('“', '"').replace('”', '"').replace("'", "'").replace("'", "'")
    return unaccent(name.strip().lower())

def to_mtgo_format(s: str) -> str:
    return s.replace(' // ', '/').replace('\n', '\r\n')
