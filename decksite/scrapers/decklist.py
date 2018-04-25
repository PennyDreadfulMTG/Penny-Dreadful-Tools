from typing import Any, Dict, List, Tuple
import re
import xml

import untangle

from decksite.data.deck import Deck
from magic import oracle
from shared.pd_exception import InvalidDataException


Section = Dict[str, int]
Decklist = Dict[str, Section]

def parse_line(line: str) -> Tuple[int, str]:
    match = re.match(r'(\d+)\s+(.*)', line)
    if match is None:
        raise InvalidDataException('No number specified with `{line}`'.format(line=line))
    else:
        n, name = re.search(r'(\d+)\s+(.*)', line).groups()
        return (int(n), name)

def parse_chunk(chunk: str, section: Section) -> None:
    for line in chunk.splitlines():
        if line.lower().strip() == 'sideboard':
            continue
        n, name = parse_line(line)
        section[name] = int(n) + section.get(name, 0)

# Read a text decklist into an intermediate dict form.
def parse(s: str) -> Decklist:
    s = s.lstrip().rstrip()
    maindeck: Dict[str, Any] = {}
    sideboard: Dict[str, Any] = {}
    chunks = re.split(r'\r?\n\r?\n|^\s*sideboard.*?\n', s, flags=re.IGNORECASE|re.MULTILINE)
    if len(chunks) > 1 and (len(chunks[-1]) > 1 or len(chunks[-1][0]) > 0) or 'Sideboard' in s:
        for chunk in chunks[:-1]:
            parse_chunk(chunk, maindeck)
        parse_chunk(chunks[-1], sideboard)
    else:
        # No empty lines or explicit "sideboard" section: gather 60 cards for maindeck from the beginning,
        # then gather 15 cards for sideboard starting from the end, then the rest to maindeck
        lines = s.splitlines()
        while sum(maindeck.values()) < 60 and len(lines) > 0:
            n, name = parse_line(lines.pop(0))
            maindeck[name] = n + maindeck.get(name, 0)

        while len(lines) > 0:
            n, name = parse_line(lines.pop(-1))
            if sum(sideboard.values()) + n <= 15:
                sideboard[name] = n + sideboard.get(name, 0)
                if sum(sideboard.values()) == 15:
                    break
            else:
                maindeck[name] = n + maindeck.get(name, 0)
                break

        while len(lines) > 0:
            n, name = parse_line(lines.pop(0))
            maindeck[name] = n + maindeck.get(name, 0)

    return {'maindeck':maindeck, 'sideboard':sideboard}


# Parse a deck in the Magic Online XML .dek format or raise an InvalidDataException.
def parse_xml(s: str) -> Decklist:
    d: Decklist = {'maindeck': {}, 'sideboard': {}}
    try:
        doc = untangle.parse(s)
        for c in doc.Deck.Cards:
            section = 'sideboard' if c['Sideboard'] == 'true' else 'maindeck'
            d[section][c['Name']] = d[section].get(c['Name'], 0) + int(c['Quantity'])
        return d
    except xml.sax.SAXException as e: # type: ignore
        raise InvalidDataException(e)

# Load the cards in the intermediate dict form.
def vivify(decklist: Decklist) -> Deck:
    validated: Decklist = {'maindeck': {}, 'sideboard': {}}
    invalid_names = set()
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
