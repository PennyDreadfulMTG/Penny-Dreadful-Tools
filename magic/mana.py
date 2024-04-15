"""
This module parses Mana Costs
"""
import itertools
import re
from collections.abc import Iterable, Sequence

from shared.pd_exception import ParseException

START = ''
DIGIT = '[0-9]'
COLOR = '[WURBGCS]'
X = '[XYZ]'
SLASH = '/'
MODIFIER = 'P'
HALF = 'H'
HYBRID = 'SPECIAL-HYBRID'

def parse(s: str) -> list[str]:
    tmp = ''
    tokens = []
    mode = START
    stripped = s.replace('{', '').replace('}', '')
    for c in list(stripped):
        if mode == START:
            if re.match(DIGIT, c):
                tmp += c
                mode = DIGIT
            elif re.match(COLOR, c):
                tmp += c
                mode = COLOR
            elif re.match(X, c):
                tokens.append(c)
                tmp = ''
                mode = START
            elif re.match(HALF, c):
                tmp += c
                mode = HALF
            else:
                raise InvalidManaCostException(f'Symbol must start with {DIGIT} or {COLOR} or {X} or {HALF}, `{c}` found in `{s}`.')
        elif mode == DIGIT:
            if re.match(DIGIT, c):
                tmp += c
            elif re.match(COLOR, c) or re.match(X, c):
                tokens.append(tmp)
                tmp = c
                mode = COLOR
            elif re.match(SLASH, c):
                tmp += c
                mode = SLASH
            else:
                raise InvalidManaCostException(f'Digit must be followed by {DIGIT}, {COLOR} or {SLASH}, `{c}` found in `{s}`.')
        elif mode == COLOR:
            if re.match(COLOR, c):
                tokens.append(tmp)
                tmp = c
                mode = COLOR
            elif re.match(SLASH, c):
                tmp += c
                mode = SLASH
            else:
                raise InvalidManaCostException(f'Color must be followed by {COLOR} or {SLASH}, `{c}` found in `{s}`.')
        elif mode == SLASH:
            if re.match(MODIFIER, c):
                tokens.append(tmp + c)
                tmp = ''
                mode = START
            elif re.match(COLOR, c):
                tmp += c
                mode = HYBRID
            else:
                raise InvalidManaCostException(f'Slash must be followed by {COLOR} or {MODIFIER}, `{c}` found in `{s}`.')
        elif mode == HALF:
            if re.match(COLOR, c):
                tokens.append(tmp + c)
                tmp = ''
                mode = START
            else:
                raise InvalidManaCostException(f'H must be followed by {COLOR}, `{c}` found in `{s}`.')
        elif mode == HYBRID:  # Having an additional check after HYBRID for a second slash accomodates hybrid phyrexian mana like Tamiyo, Compleated Sage
            if re.match(SLASH, c):
                tmp += c
                mode = SLASH
            elif re.match(DIGIT, c):
                tokens.append(tmp)
                tmp = c
                mode = DIGIT
            elif re.match(COLOR, c):
                tokens.append(tmp)
                tmp = c
                mode = COLOR
            elif re.match(X, c):
                tokens.append(tmp)
                tokens.append(c)
                tmp = ''
                mode = START
            elif re.match(HALF, c):
                tokens.append(tmp)
                tmp = c
                mode = HALF
            else:
                raise InvalidManaCostException(f'Hybrid must be followed by {SLASH} or {DIGIT} or {COLOR} or {X} or {HALF}, `{c}` found in `{s}`.')
    if tmp:
        tokens.append(tmp)
    return tokens

def colors(symbols: list[str]) -> dict[str, set[str]]:
    return colors_from_colored_symbols(colored_symbols(symbols))

def colors_from_colored_symbols(all_colored_symbols: dict[str, list[str]]) -> dict[str, set[str]]:
    return {'required': set(all_colored_symbols['required']), 'also': set(all_colored_symbols['also'])}

def colored_symbols(symbols: list[str]) -> dict[str, list[str]]:
    cs: dict[str, list[str]] = {'required': [], 'also': []}
    for symbol in symbols:
        if generic(symbol) or variable(symbol):
            pass
        elif hybrid(symbol):
            parts = symbol.split(SLASH)
            cs['also'].append(parts[0])
            cs['also'].append(parts[1])
        elif phyrexian(symbol):
            cs['also'].append(symbol[0])
        elif twobrid(symbol):
            parts = symbol.split(SLASH)
            cs['also'].append(parts[1])
        elif colored(symbol):
            cs['required'].append(symbol)
        else:
            raise InvalidManaCostException(f'Unrecognized symbol type: `{symbol}` in `{symbols}`')
    return cs

def cmc(mana_cost: str) -> float:
    symbols = parse(mana_cost)
    total = 0.0
    for symbol in symbols:
        if generic(symbol):
            total += int(symbol)
        elif twobrid(symbol):
            total += 2.0
        elif half(symbol):
            total += 0.5
        elif variable(symbol):
            total += 0.0
        elif phyrexian(symbol) or hybrid(symbol) or colored(symbol):
            total += 1.0
        else:
            raise InvalidManaCostException(f"Can't calculate CMC - I don't recognize '{symbol}'")
    return total

def generic(symbol: str) -> bool:
    return bool(re.match(f'^{DIGIT}+$', symbol))

def variable(symbol: str) -> bool:
    return bool(re.match(f'^{X}$', symbol))

def phyrexian(symbol: str) -> bool:
    return bool(re.match('^({color}/)?{color}/{modifier}$'.format(color=COLOR, modifier=MODIFIER), symbol))

def hybrid(symbol: str) -> bool:
    return bool(re.match('^{color}/{color}(/{modifier})?$'.format(color=COLOR, modifier=MODIFIER), symbol))

def twobrid(symbol: str) -> bool:
    return bool(re.match(f'^2/{COLOR}$', symbol))

def half(symbol: str) -> bool:
    return bool(re.match(f'^{HALF}{COLOR}$', symbol))

def colored(symbol: str) -> bool:
    return bool(re.match(f'^{COLOR}$', symbol))

def has_x(mana_cost: str) -> bool:
    return len([symbol for symbol in parse(mana_cost) if variable(symbol)]) > 0

def order(symbols: Iterable[str]) -> list[str]:
    permutations = itertools.permutations(symbols)
    return list(sorted(permutations, key=order_score)[0])

def order_score(initial_symbols: tuple[str, ...]) -> int:
    symbols = [symbol for symbol in initial_symbols if symbol not in ('C', 'S')]
    if not symbols:
        return 0
    score = 100  # Start at 100 so that subtracting for Colorless and Snow don't take us below 0.
    positions = ['W', 'U', 'B', 'R', 'G']
    current = positions.index(symbols[0])
    for symbol in symbols[1:]:
        position = positions.index(symbol)
        distance = position - current
        if position < current:
            distance += len(positions)
        score += distance
        current = position
    score = score * 10 + positions.index(symbols[0])
    # Prefer Colorless and Snow at the end.
    if 'C' in initial_symbols:
        score -= initial_symbols.index('C')
    if 'S' in initial_symbols:
        score -= initial_symbols.index('S') * 2
    return score

def sort_score(initial_symbols: Sequence[str]) -> int:
    positions = ['C', 'S', 'W', 'U', 'B', 'R', 'G']
    symbols = set(initial_symbols)
    # The dominant factor in ordering is how many colors are in the deck. All 2 color decks sort after all 1 color decks, etc.
    # Colorless and Snow are not considered a color but add a little to the score so that W+C or W+S sort after just W.
    num_colors = len([symbol for symbol in symbols if symbol in ['W', 'U', 'B', 'R', 'G']])
    score = num_colors * pow(2, len(positions))
    for symbol in symbols:
        score += pow(2, positions.index(symbol))
    return score

class InvalidManaCostException(ParseException):
    pass
