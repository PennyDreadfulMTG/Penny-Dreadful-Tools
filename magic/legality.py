from magic.database import db

FORMATS = set()

def legal_formats(d):
    if sum(e['n'] for e in d.maindeck) < 60:
        return set()
    if sum(e['n'] for e in d.sideboard) > 15:
        return set()
    card_count = {}
    for c in d.all_cards():
        if not c.type.startswith('Basic Land'):
            card_count[c.name] = card_count.get(c.name, 0) + 1
    if card_count.values() and max(card_count.values()) > 4:
        return set()
    formats = FORMATS.copy()
    assert len(formats) > 0
    formats.discard('Commander')
    for c in d.all_cards():
        for f in formats.copy():
            if f not in c.legalities.keys() or c.legalities[f] == 'Banned':
                formats.discard(f)
                if not formats:
                    return formats
    return formats

def init():
    FORMATS.clear()
    for v in db().values('SELECT name FROM format'):
        FORMATS.add(v)

init()
