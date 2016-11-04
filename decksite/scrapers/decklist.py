import re

from magic import oracle
from shared.pd_exception import InvalidDataException

from decksite.data.deck import Deck

# Read a text decklist into an intermediate dict form.
def parse(s):
    d = {'maindeck': {}, 'sideboard': {}}
    part = 'maindeck'
    for line in s.splitlines():
        if line.startswith('Sideboard'):
            part = 'sideboard'
        elif line.strip() == '':
            pass
        elif not re.match(r'\d', line):
            raise InvalidDataException('No number specified with `{line}`'.format(line=line))
        else:
            try:
                n, name = re.search(r'(\d+)\s+(.*)', line).groups()
                d[part][name] = int(n)
            except AttributeError:
                raise InvalidDataException('Unable to parse `{line}`'.format(line=line))
    return d

# Load the cards in the intermediate dict form.
def vivify(decklist):
    validated, invalid_names = {'maindeck': {}, 'sideboard': {}}, set()
    for section in ['maindeck', 'sideboard']:
        for name, n in decklist[section].items():
            try:
                validated[section][oracle.valid_name(name)] = n
            except InvalidDataException:
                invalid_names.add(name)
    if invalid_names:
        raise InvalidDataException('Invalid cards: {invalid_names}'.format(invalid_names='; '.join(invalid_names)))
    validated_names = list(validated['maindeck'].keys()) + list(validated['sideboard'].keys())
    cards = {c.name: c for c in oracle.load_cards(validated_names)}
    d = Deck({'maindeck': [], 'sideboard': []})
    for section in ['maindeck', 'sideboard']:
        for name, n in validated[section].items():
            d[section].append({'n': n, 'name': name, 'card': cards[name]})
    return d
