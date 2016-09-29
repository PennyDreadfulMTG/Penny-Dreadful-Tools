import types

def properties():
    return {
        'system_id': 'TEXT',
        'layout': 'TEXT',
        'name': 'TEXT',
        'mana_cost': 'TEXT',
        'cmc': 'REAL',
        'type': 'TEXT',
        'text': 'TEXT',
        'flavor': 'TEXT',
        'artist': 'TEXT',
        'number': 'TEXT',
        'power': 'TEXT',
        'toughness': 'TEXT',
        'loyalty': 'TEXT',
        'multiverse_id': 'INTEGER',
        'image_name': 'TEXT',
        'watermark': 'TEXT',
        'border': 'TEXT',
        'timeshifted': 'INTEGER',
        'hand': 'INTEGER',
        'life': 'INTEGER',
        'reserved': 'INTEGER',
        'release_date': 'INTEGER',
        'starter': 'INTEGER',
        'mci_number': 'TEXT'
    }

class Card(types.SimpleNamespace):
    def __init__(self, params):
        super().__init__()
        for k in params.keys():
            setattr(self, k, params[k])
