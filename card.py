import types

def card_properties():
    return {
        'layout': 'TEXT'
    }

def face_properties():
    return {
        'name': 'TEXT',
        'mana_cost': 'TEXT',
        'cmc': 'REAL',
        'power': 'TEXT',
        'toughness': 'TEXT',
        'loyalty': 'TEXT',
        'type': 'TEXT',
        'text': 'TEXT',
        'image_name': 'TEXT',
        'hand': 'INTEGER',
        'life': 'INTEGER',
        'starter': 'INTEGER'
    }

def set_properties():
    return {
        'name': 'TEXT',
        'code': 'TEXT',
        'gatherer_code': 'TEXT',
        'old_code': 'TEXT',
        'magiccardsinfo_code': 'TEXT',
        'release_date': 'INT',
        'border': 'TEXT',
        'type': 'TEXT',
        'online_only': 'INT'
    }

def printing_properties():
    return {
        'system_id': 'TEXT',
        'rarity': 'TEXT',
        'flavor': 'TEXT',
        'artist': 'TEXT',
        'number': 'TEXT',
        'multiverseid': 'TEXT',
        'watermark': 'TEXT',
        'border': 'TEXT',
        'timeshifted': 'INTEGER',
        'reserved': 'INTEGER',
        'mci_number': 'TEXT'
    }

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
