import copy
import unicodedata
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, cast

from shared import dtutil
from shared.container import Container

# Properties of the various aspects of cards with information about how to store and retrieve them from the database.

BOOLEAN = 'BOOLEAN'
DATE = 'INTEGER'
INTEGER = 'INTEGER'
REAL = 'REAL'
TEXT = 'LONGTEXT'
VARCHAR = 'VARCHAR(190)'

BASE = {
    'type': VARCHAR,
    'nullable': True,
    'primary_key': False,
    'query': '`{table}`.`{column}` AS `{column}`',
    'mtgjson': True,
    'foreign_key': None,
    'default': None,
    'unique': False,
    'unique_with': None
}

def card_properties():
    props = {}
    for k in ['id', 'layout']:
        props[k] = copy.deepcopy(BASE)
    props['id']['type'] = INTEGER
    props['id']['nullable'] = False
    props['id']['primary_key'] = True
    props['id']['mtgjson'] = False
    props['layout']['nullable'] = False
    return props

def face_properties():
    props = {}
    base = copy.deepcopy(BASE)
    base['query'] = "GROUP_CONCAT(CASE WHEN `{table}`.position = 1 THEN `{table}`.`{column}` ELSE '' END SEPARATOR '') AS `{column}`"
    for k in ['id', 'name', 'mana_cost', 'cmc', 'power', 'toughness', 'power', 'toughness', 'loyalty', 'type', 'text', 'search_text', 'image_name', 'hand', 'life', 'starter', 'position', 'name_ascii', 'card_id']:
        props[k] = copy.deepcopy(base)
    for k in ['id', 'position', 'name_ascii', 'card_id', 'search_text']:
        props[k]['mtgjson'] = False
    for k in ['id', 'name', 'type', 'text', 'search_text']:
        props[k]['nullable'] = False
    for k in ['id', 'card_id', 'hand', 'life', 'starter']:
        props[k]['type'] = INTEGER
    props['id']['primary_key'] = True
    props['id']['query'] = '`{table}`.`{column}` AS face_id'
    props['cmc']['type'] = REAL
    props['name']['query'] = """{name_query} AS name""".format(name_query=name_query())
    props['name_ascii']['query'] = """{name_query} AS name_ascii""".format(name_query=name_query('name_ascii'))
    props['cmc']['query'] = """{cmc_query} AS cmc""".format(cmc_query=cmc_query())
    props['mana_cost']['query'] = "GROUP_CONCAT(`{table}`.`{column}` SEPARATOR '|') AS `{column}`"
    props['type']['query'] = """{type_query} AS type""".format(type_query=type_query())
    for k in ['text', 'search_text']:
        props[k]['query'] = "GROUP_CONCAT(`{table}`.`{column}` SEPARATOR '\n-----\n') AS `{column}`"
        props[k]['type'] = TEXT
    props['card_id']['foreign_key'] = ('card', 'id')
    return props

def set_properties():
    props = {}
    for k in ['id', 'name', 'code', 'gatherer_code', 'old_code', 'magiccardsinfo_code', 'release_date', 'border', 'type', 'online_only']:
        props[k] = copy.deepcopy(BASE)
    for k in ['id', 'name', 'code', 'release_date', 'border', 'type']:
        props[k]['nullable'] = False
    props['id']['primary_key'] = True
    props['id']['type'] = INTEGER
    props['id']['mtgjson'] = False
    props['release_date']['type'] = DATE
    props['online_only']['type'] = BOOLEAN
    props['name']['unique'] = True
    props['code']['unique'] = True
    props['gatherer_code']['unique'] = True
    props['old_code']['unique'] = True
    props['magiccardsinfo_code']['unique'] = True
    return props

def printing_properties():
    props = {}
    for k in ['id', 'system_id', 'rarity', 'flavor', 'artist', 'number', 'multiverseid', 'watermark', 'border', 'timeshifted', 'reserved', 'mci_number', 'card_id', 'set_id', 'rarity_id']:
        props[k] = copy.deepcopy(BASE)
    for k in ['id', 'system_id', 'rarity', 'artist', 'card_id', 'set_id']:
        props[k]['nullable'] = False
    for k in ['id', 'card_id', 'set_id', 'rarity_id']:
        props[k]['type'] = INTEGER
        props[k]['mtgjson'] = False
    props['id']['primary_key'] = True
    props['id']['nullable'] = False
    props['timeshifted']['type'] = BOOLEAN
    props['reserved']['type'] = BOOLEAN
    props['card_id']['foreign_key'] = ('card', 'id')
    props['set_id']['foreign_key'] = ('set', 'id')
    props['rarity_id']['foreign_key'] = ('rarity', 'id')
    props['flavor']['type'] = TEXT
    return props

def color_properties():
    props = {}
    for k in ['id', 'name', 'symbol']:
        props[k] = copy.deepcopy(BASE)
        props[k]['nullable'] = False
    props['id']['type'] = INTEGER
    props['id']['primary_key'] = True
    return props

def card_color_properties():
    props = {}
    for k in ['id', 'card_id', 'color_id']:
        props[k] = copy.deepcopy(BASE)
        props[k]['type'] = INTEGER
        props[k]['nullable'] = False
    props['id']['primary_key'] = True
    props['card_id']['unique_with'] = ['color_id']
    props['card_id']['foreign_key'] = ('card', 'id')
    props['color_id']['foreign_key'] = ('color', 'id')
    return props

def card_type_properties(typetype):
    props = {}
    for k in ['id', 'card_id', typetype]:
        props[k] = copy.deepcopy(BASE)
        props[k]['nullable'] = False
    props['id']['type'] = INTEGER
    props['id']['primary_key'] = True
    props['card_id']['type'] = INTEGER
    props['card_id']['foreign_key'] = ('card', 'id')
    return props

def format_properties():
    props = {}
    for k in ['id', 'name']:
        props[k] = copy.deepcopy(BASE)
        props[k]['nullable'] = False
    props['id']['type'] = INTEGER
    props['id']['primary_key'] = True
    return props

def card_legality_properties():
    props = {}
    for k in ['id', 'card_id', 'format_id', 'legality']:
        props[k] = copy.deepcopy(BASE)
        props[k]['nullable'] = False
    props['id']['type'] = INTEGER
    props['id']['primary_key'] = True
    props['card_id']['type'] = INTEGER
    props['card_id']['foreign_key'] = ('card', 'id')
    props['format_id']['type'] = INTEGER
    props['format_id']['foreign_key'] = ('format', 'id')
    props['legality']['nullable'] = True
    return props

def card_alias_properties():
    props = {}
    for k in ['id', 'card_id', 'alias']:
        props[k] = copy.deepcopy(BASE)
        props[k]['nullable'] = False
    props['id']['type'] = INTEGER
    props['id']['primary_key'] = True
    props['card_id']['type'] = INTEGER
    props['card_id']['foreign_key'] = ('card', 'id')
    return props

def card_bug_properties():
    props = {}
    for k in ['id', 'card_id', 'description', 'classification', 'last_confirmed', 'url', 'from_bug_blog']:
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
    return props

def name_query(column: str = 'face_name') -> str:
    return """
        CASE
        WHEN layout = 'double-faced' OR layout = 'flip' THEN
            GROUP_CONCAT(CASE WHEN `{table}`.position = 1 THEN {column} ELSE '' END SEPARATOR '')
        WHEN layout = 'meld' THEN
            GROUP_CONCAT(CASE WHEN `{table}`.position = 1 OR `{table}`.position = 2 THEN {column} ELSE '' END SEPARATOR '')
        ELSE
            GROUP_CONCAT({column} SEPARATOR ' // ' )
        END
    """.format(column=column, table='{table}')

def cmc_query() -> str:
    return """
        CASE
        WHEN layout = 'split' OR layout = 'aftermath' THEN
            SUM(`{table}`.cmc)
        WHEN layout = 'meld' THEN
            SUM(CASE WHEN `{table}`.position = 1 OR `{table}`.position = 2 THEN {column} ELSE 0 END)
        ELSE
            SUM(CASE WHEN `{table}`.position = 1 THEN `{table}`.cmc ELSE 0 END)
        END
    """

def type_query() -> str:
    return """
        CASE
        WHEN layout = 'meld' THEN
            GROUP_CONCAT(CASE WHEN `{table}`.position = 1 OR `{table}`.position = 2 THEN {column} ELSE '' END SEPARATOR '')
        ELSE
            GROUP_CONCAT(CASE WHEN `{table}`.position = 1 THEN {column} ELSE '' END SEPARATOR '')
        END
    """

def unaccent(s: str) -> str:
    return ''.join((c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn'))

def canonicalize(name: str) -> str:
    if name.find('/') >= 0 and name.find('//') == -1:
        name = name.replace('/', '//')
    if name.find('//') >= 0 and name.find(' // ') == -1:
        name = name.replace('//', ' // ')
    # Replace ligature and smart quotes.
    name = name.replace('Æ', 'Ae').replace('“', '"').replace('”', '"').replace("'", "'").replace("'", "'")
    return unaccent(name.strip().lower())

def to_mtgo_format(s):
    return s.replace(' // ', '/').replace('\n', '\r\n')

class Card(Container):
    def __init__(self, params) -> None:
        super().__init__()
        for k in params.keys():
            setattr(self, k, determine_value(k, params))
        if not self.names:
            setattr(self, 'names', [self.name])

    def is_creature(self):
        return 'Creature' in self.type

    def is_land(self):
        return 'Land' in self.type

    def is_spell(self):
        return not self.is_creature() and not self.is_land()

    def is_split(self):
        return self.name.find('//') >= 0

def determine_value(k: str, params) -> Any:
    v = params[k]
    if k == 'names' or k == 'mana_cost':
        return cast(str, v).split('|') if v is not None else None
    elif k == 'legalities':
        v = determine_legalities(cast(str, v))
    elif k == 'bugs':
        v = determine_bugs(cast(str, v))
    return v

def determine_legalities(s: Optional[str]) -> Dict[str, str]:
    if s is None:
        return {}
    formats = s.split(',')
    v = {}
    for f in formats:
        name, status = f.split(':')
        v[name] = status
    return v

def determine_bugs(s: Optional[str]) -> Optional[List[Dict[str, Union[str, datetime, bool]]]]:
    if s is None:
        return None
    bugs = s.split('_SEPARATOR_')
    v = []
    for b in bugs:
        description, classification, last_confirmed, url, from_bug_blog = b.split('|')
        bb = from_bug_blog == '1'
        v.append({'description': description, 'classification': classification, 'last_confirmed': dtutil.ts2dt(float(last_confirmed)), 'url': url, 'from_bug_blog': bb})
        return v
    return None

class Printing(Container):
    pass
