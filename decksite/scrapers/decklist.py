import re
import xml

import untangle

from magic import oracle
from shared.pd_exception import InvalidDataException

from decksite.data.deck import Deck

# Read a text decklist into an intermediate dict form.
def parse(s):
    d = {'maindeck': {}, 'sideboard': {}}
    last_chunk = {}
    section = 'maindeck'
    for line in s.splitlines():
        if line.strip() == '':
            last_chunk = {}
        if line.lower().startswith('sideboard') or (line.strip() == '' and s.count('\n\n') == 1 and len(d['maindeck']) > 0):
            section = 'sideboard'
        elif line.strip() == '':
            pass
        elif not re.match(r'\d', line):
            raise InvalidDataException('No number specified with `{line}`'.format(line=line))
        else:
            try:
                n, name = re.search(r'(\d+)\s+(.*)', line).groups()
                # Although it seems nonsensical to add cards here because that must mean we are in a sideboard
                # our backtracking sideboard finder will deal with it momentarily.
                d[section][name] = int(n) + d[section].get(name, 0)
                last_chunk[name] = int(n)
            except AttributeError:
                raise InvalidDataException('Unable to parse `{line}`'.format(line=line))
    # Heuristic to find a sideboard. Could very well be broken with Battle of Wits and similar.
    if not d['sideboard'] and sum(d['maindeck'].values()) > 60 and sum(last_chunk.values()) <= 15:
        d['sideboard'] = last_chunk
        for name, count in last_chunk.items():
            d['maindeck'][name] -= count
            if d['maindeck'][name] == 0:
                del d['maindeck'][name]
    return d

# Parse a deck in the MTGO XML .dek format or raise an InvalidDataException.
def parse_xml(s):
    d = {'maindeck': {}, 'sideboard': {}}
    try:
        doc = untangle.parse(s)
        for c in doc.Deck.Cards:
            section = 'sideboard' if c['Sideboard'] == 'true' else 'maindeck'
            d[section][c['Name']] = int(c['Quantity'])
        return d
    except xml.sax.SAXException as e:
        raise InvalidDataException(e)

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
