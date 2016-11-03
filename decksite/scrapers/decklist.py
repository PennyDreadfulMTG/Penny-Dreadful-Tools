import re

from magic import oracle
from shared.pd_exception import InvalidDataException

from decksite.data.deck import Deck

def parse_and_vivify(s):
    return vivify(parse(s))

def vivify(decklist):
    names = [name for name in decklist['maindeck'].keys()] + [name for name in decklist['sideboard'].keys()]
    cards = {card.name: card for card in oracle.load_cards(names)}
    d = Deck({'maindeck': [], 'sideboard': []})
    for name, n in decklist['maindeck'].items():
        d.maindeck.append({'n': n, 'name': name, 'card': cards[name]})
    for name, n in decklist['sideboard'].items():
        d.sideboard.append({'n': n, 'name': name, 'card': cards[name]})
    return d

def parse(s):
    d = {'maindeck': {}, 'sideboard': {}}
    part = 'maindeck'
    for line in s.splitlines():
        if line.startswith('Sideboard'):
            part = 'sideboard'
        elif line.strip() == '':
            pass
        else:
            try:
                n, card = re.search(r'(\d+)\s+(.*)', line).groups()
                d[part][card] = int(n)
            except AttributeError:
                raise InvalidDataException('Unable to parse {line}'.format(line=line))
    return d
