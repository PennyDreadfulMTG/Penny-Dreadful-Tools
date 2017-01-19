from magic.database import db
from magic import oracle, multiverse

FORMATS = set()

def legal_in_format(d, f):
    return f in legal_formats(d, [f])

def legal_formats(d, formats_to_check=None):
    if formats_to_check is None:
        formats_to_check = FORMATS
    formats = formats_to_check.copy()
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
    formats.discard('Commander')
    for c in d.all_cards():
        for f in formats.copy():
            if f not in c.legalities.keys() or c.legalities[f] == 'Banned':
                formats.discard(f)
            elif c.legalities[f] == 'Restricted':
                if card_count[c.name] > 1:
                    formats.discard(f)
            if not formats:
                return formats

    return formats

def init():
    assert len(oracle.legal_cards()) > 0
    all_known = oracle.load_card('island').legalities
    if not 'Penny Dreadful EMN' in all_known:
        multiverse.set_legal_cards(season='EMN')
    if not 'Penny Dreadful KLD' in all_known:
        multiverse.set_legal_cards(season='KLD')

    FORMATS.clear()
    for v in db().values('SELECT name FROM format'):
        FORMATS.add(v)

init()
