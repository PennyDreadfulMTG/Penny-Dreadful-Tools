import re
import xml
from typing import Any, Dict, Tuple

import untangle

from magic import oracle
from magic.models import CardRef, Deck
from shared.pd_exception import InvalidDataException

SectionType = Dict[str, int]
DecklistType = Dict[str, SectionType]

def parse_line(line: str) -> Tuple[int, str]:
    match = re.match(r'(\d+)\s+(.*)', line)
    if match is None:
        raise InvalidDataException('No number specified with `{line}`'.format(line=line))
    else:
        n, name = match.groups()
        return (int(n), name)

def parse_chunk(chunk: str, section: SectionType) -> None:
    for line in chunk.splitlines():
        if line.lower().strip() == 'sideboard':
            continue
        n, name = parse_line(line)
        section[name] = int(n) + section.get(name, 0)

# Read a text decklist into an intermediate dict form.
def parse(s: str) -> DecklistType:
    s = s.lstrip().rstrip()
    if looks_doublespaced(s):
        s = remove_doublespacing(s)
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

        # But Commander decks are special so undo our trickery if we have exactly 100 cards and it is singleton except basics.
        if sum(maindeck.values()) + sum(sideboard.values()) == 100:
            new_maindeck, is_commander = {}, True
            for name in set(maindeck) | set(sideboard):
                new_maindeck[name] = maindeck.get(name, 0) + sideboard.get(name, 0)
                if new_maindeck[name] > 1 and name not in ['Plains', 'Island', 'Swamp', 'Mountain', 'Forest', 'Wastes']:
                    is_commander = False
            if is_commander:
                maindeck = new_maindeck
                sideboard = {}

    return {'maindeck':maindeck, 'sideboard':sideboard}

def looks_doublespaced(s: str) -> bool:
    return len(re.findall(r'\r?\n\r?\n', s)) >= len(re.findall(r'\r?\n', s)) / 2 - 1

def remove_doublespacing(s: str) -> str:
    return re.sub(r'\r?\n\r?\n', '\n', s)

# Parse a deck in the Magic Online XML .dek format or raise an InvalidDataException.
def parse_xml(s: str) -> DecklistType:
    d: DecklistType = {'maindeck': {}, 'sideboard': {}}
    try:
        doc = untangle.parse(s)
        for c in doc.Deck.Cards:
            section = 'sideboard' if c['Sideboard'] == 'true' else 'maindeck'
            d[section][c['Name']] = d[section].get(c['Name'], 0) + int(c['Quantity'])
        return d
    except xml.sax.SAXException as e: # type: ignore
        raise InvalidDataException(e)
    except AttributeError as e:
        raise InvalidDataException(e) # Not valid MTGO .deck format

# Load the cards in the intermediate dict form.
def vivify(decklist: DecklistType) -> Deck:
    validated: DecklistType = {'maindeck': {}, 'sideboard': {}}
    invalid_names = set()
    for section in ['maindeck', 'sideboard']:
        for name, n in decklist[section].items():
            try:
                validated[section][oracle.valid_name(name)] = n
            except InvalidDataException:
                invalid_names.add(name)
    if invalid_names:
        raise InvalidDataException('Invalid cards: {invalid_names}'.format(invalid_names='; '.join(invalid_names)))
    d = Deck({'maindeck': [], 'sideboard': []})
    for section in ['maindeck', 'sideboard']:
        for name, n in validated[section].items():
            d[section].append(CardRef(name, n))
    return d
