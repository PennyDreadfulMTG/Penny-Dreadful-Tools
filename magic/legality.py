from magic.database import db
from magic import oracle, multiverse

FORMATS = set()

def legal_in_format(d, f):
    return f in legal_formats(d, [f])

def legal_formats(d, formats_to_check=None, errors=None):
    init()
    if formats_to_check is None:
        formats_to_check = FORMATS
    if errors is None:
        errors = {}
    formats = formats_to_check.copy()
    if sum(e['n'] for e in d.maindeck) < 60:
        for f in formats_to_check:
            errors[f] = 'You have less than 60 cards.'
        return set()
    if sum(e['n'] for e in d.sideboard) > 15:
        for f in formats_to_check:
            errors[f] = 'You have more than 15 cards in your sideboard.'
        return set()
    if (sum(e['n'] for e in d.maindeck) + sum(e['n'] for e in d.sideboard)) != 100:
        formats.discard('Commander')
        errors['Commander'] = 'Incorrect deck size.'
    card_count = {}
    for c in d.all_cards():
        if not c.type.startswith('Basic Land'):
            card_count[c.name] = card_count.get(c.name, 0) + 1
    if card_count.values() and max(card_count.values()) > 4:
        for f in formats_to_check:
            errors[f] = 'You have more than four copies of a card.'
        return set()
    elif card_count.values() and max(card_count.values()) > 1:
        formats.discard('Commander')
        errors['Commander'] = 'Deck is not Singleton.'
    for c in d.all_cards():
        for f in formats.copy():
            if f not in c.legalities.keys() or c.legalities[f] == 'Banned':
                formats.discard(f)
                illegal = 'banned' if c.legalities.get(f, None) == 'Banned' else 'not legal'
                errors[f] = '{c} is {illegal}.'.format(c=c.name, illegal=illegal)
            elif c.legalities[f] == 'Restricted':
                if card_count[c.name] > 1:
                    formats.discard(f)
                    errors[f] = '{c} is restricted.'.format(c=c.name)
            if not formats:
                return formats

    return formats

def init():
    if FORMATS:
        return
    print('Updating Legalities...')
    assert len(oracle.legal_cards()) > 0
    all_known = oracle.load_card('island').legalities
    if not 'Penny Dreadful EMN' in all_known:
        multiverse.set_legal_cards(season='EMN')
    if not 'Penny Dreadful KLD' in all_known:
        multiverse.set_legal_cards(season='KLD')
    if not 'Penny Dreadful AER' in all_known:
        multiverse.set_legal_cards(season='AER')

    FORMATS.clear()
    for v in db().values('SELECT name FROM format'):
        FORMATS.add(v)
