import copy
import types

"""Properties of the various aspects of cards with information about how to store and retrieve them from the database."""

BOOLEAN = 'INTEGER'
DATE    = 'INTEGER'
INTEGER = 'INTEGER'
REAL    = 'REAL'
TEXT    = 'TEXT'

BASE = {
    'type': TEXT,
    'nullable': True,
    'primary_key': False,
    'select': '`{table}`.`{column}`',
    'mtgjson': True
}

def card_properties():
    props = {}
    for k in ['id', 'pd_legal', 'layout']:
        props[k] = copy.deepcopy(BASE)
    for k in ['id', 'pd_legal']:
        props[k]['mtgjson'] = False
    props['id']['type'] = INTEGER
    props['id']['nullable'] = False
    props['id']['primary_key'] = True
    props['pd_legal']['type'] = BOOLEAN
    props['pd_legal']['nullable'] = False
    return props

def face_properties():
    props = {}
    base = copy.deepcopy(BASE)
    base['select'] = "GROUP_CONCAT(CASE WHEN `{table}`.position = 1 THEN `{table}`.`{column}` ELSE '' END, '') AS `{column}`"
    for k in ['id', 'name', 'mana_cost', 'cmc', 'power', 'toughness', 'power', 'toughness', 'loyalty', 'type', 'text', 'image_name', 'hand', 'life', 'starter', 'position', 'name_ascii']:
        props[k] = copy.deepcopy(base)
    for k in ['id', 'position', 'name_ascii']:
        props[k]['mtgjson'] = False
    for k in ['id', 'name', 'cmc', 'type', 'text']:
        props[k]['nullable'] = False
    for k in ['hand', 'life', 'starter']:
        props[k]['type'] = INTEGER
    props['id']['primary_key'] = True
    props['cmc']['type'] = REAL
    props['name']['select'] = """CASE WHEN layout = 'meld' OR layout = 'double-faced' THEN
            GROUP_CONCAT(CASE WHEN `{table}`.position = 1 THEN face_name ELSE '' END, '')
        ELSE
            GROUP_CONCAT(face_name , ' // ' )
        END AS name"""
    props['mana_cost']['select'] = """CASE
            WHEN layout IN ('split') AND `{table}`.`text` LIKE '%Fuse (You may cast one or both halves of this card from your hand.)%' THEN
                GROUP_CONCAT(`{table}`.`{column}`, '')
            WHEN layout IN ('split') THEN
                NULL
            ELSE
                GROUP_CONCAT(CASE WHEN position = 1 THEN `{table}`.`{column}` ELSE '' END, '')
        END AS {column}"""
    props['cmc']['select'] = 'SUM({column}) AS `{column}`'
    props['text']['select'] = "GROUP_CONCAT({table}.`{column}`, '\n-----\n') AS `{column}`"
    return props

def set_properties():
    props = {}
    for k in ['id', 'name', 'code' 'gatherer_code', 'old_code', 'magiccardsinfo_code', 'release_date', 'border', 'type', 'online_only']:
        props[k] = copy.deepcopy(BASE)
    props['id']['primary_key'] = True
    props['id']['nullable'] = False
    props['id']['mtgjson'] = False
    props['release_date']['type'] = DATE
    props['release_date']['online_only'] = BOOLEAN
    return props

def printing_properties():
    props = {}
    for k in ['id', 'system_id', 'rarity', 'flavor', 'artist', 'number', 'multiverseid', 'watermark', 'border', 'timeshifted', 'reserved', 'mci_number']:
        props[k] = copy.deepcopy(BASE)
    props['id']['primary_key'] = True
    props['id']['nullable'] = False
    props['id']['mtgjson'] = False
    props['timeshifted']['type'] = BOOLEAN
    props['reserved']['type'] = BOOLEAN
    return props

class Card(types.SimpleNamespace):
    def __init__(self, params):
        super().__init__()
        for k in params.keys():
            v = params[k]
            if k == 'names':
                v = v.split('|')
            setattr(self, k, v)
        if not self.names:
            setattr(self, 'names', [self.name])

class Printing(types.SimpleNamespace):
    def __init__(self, params):
        super().__init__()
        for k in params.keys():
            setattr(self, k, params[k])
