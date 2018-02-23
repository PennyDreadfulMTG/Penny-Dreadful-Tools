from typing import Set

from magic import multiverse, oracle
from magic.database import db

FORMATS: Set[str] = set()

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
        if not c.type.startswith('Basic ') and not 'A deck can have any number of cards named' in c.text:
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

def cards_legal_in_format(cardlist, f):
    init()
    results = []
    for c in cardlist:
        if f in c.legalities.keys() and c.legalities[f] != 'Banned':
            results.append(c)
    return results

def order_score(fmt):
    if fmt == 'Penny Dreadful':
        return 1
    elif 'Penny Dreadful' in fmt:
        return 1000 - multiverse.SEASONS.index(fmt.replace('Penny Dreadful ', ''))
    elif fmt == 'Vintage':
        return 10000
    elif fmt == 'Legacy':
        return 100000
    elif fmt == 'Modern':
        return 1000000
    elif fmt == 'Standard':
        return 10000000
    elif 'Block' in fmt:
        return 100000000
    elif fmt == 'Commander':
        return 1000000000
    return 10000000000

def init():
    if FORMATS:
        return
    print('Updating Legalities…')
    assert len(oracle.legal_cards()) > 0
    all_known = oracle.load_card('island').legalities
    # assert 'Penny Dreadful EMN' in all_known
    assert 'Penny Dreadful' in all_known
    assert 'Vintage' in all_known

    FORMATS.clear()
    for v in db().values('SELECT name FROM format'):
        FORMATS.add(v)
