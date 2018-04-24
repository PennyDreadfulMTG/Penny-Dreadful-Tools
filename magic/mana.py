import itertools
import re
from typing import Dict, Iterable, List, Set

from shared.pd_exception import ParseException

START = ''
DIGIT = '[0-9]'
COLOR = '[WURBGC]'
X = '[XYZ]'
SLASH = '/'
MODIFIER = 'P'
HALF = '[wh]'

def parse(s) -> List[str]:
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
            elif re.match(X, c) or re.match(HALF, c):
                tokens.append(c)
                tmp = ''
                mode = START
            else:
                raise InvalidManaCostException('Symbol must start with {digit} or {color}, `{c}` found in `{s}`.'.format(digit=DIGIT, color=COLOR, c=c, s=s))
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
                raise InvalidManaCostException('Digit must be followed by {digit}, {color} or {slash}, `{c}` found in `{s}`.'.format(digit=DIGIT, color=COLOR, slash=SLASH, c=c, s=s))
        elif mode == COLOR:
            if re.match(COLOR, c):
                tokens.append(tmp)
                tmp = c
                mode = COLOR
            elif re.match(SLASH, c):
                tmp += c
                mode = SLASH
            else:
                raise InvalidManaCostException('Color must be followed by {color} or {slash}, `{c}` found in `{s}`.'.format(color=COLOR, slash=SLASH, c=c, s=s))
        elif mode == SLASH:
            if re.match(COLOR, c) or re.match(MODIFIER, c):
                tokens.append(tmp + c)
                tmp = ''
                mode = START
            else:
                raise InvalidManaCostException('Slash must be followed by {color} or {modifier}, `{c}` found in `{s}`.'.format(color=COLOR, modifier=MODIFIER, c=c, s=s))
    if tmp:
        tokens.append(tmp)
    return tokens

def colors(symbols) -> Dict[str, Set[str]]:
    return colors_from_colored_symbols(colored_symbols(symbols))

def colors_from_colored_symbols(all_colored_symbols) -> Dict[str, Set[str]]:
    return {'required': set(all_colored_symbols['required']), 'also': set(all_colored_symbols['also'])}

def colored_symbols(symbols) -> Dict[str, List[str]]:
    cs: Dict[str, List[str]] = {'required': [], 'also': []}
    for symbol in symbols:
        if generic(symbol) or variable(symbol):
            pass
        elif phyrexian(symbol):
            cs['also'].append(symbol[0])
        elif hybrid(symbol):
            parts = symbol.split(SLASH)
            cs['also'].append(parts[0])
            cs['also'].append(parts[1])
        elif twobrid(symbol):
            parts = symbol.split(SLASH)
            cs['also'].append(parts[1])
        elif colored(symbol):
            cs['required'].append(symbol)
        else:
            raise InvalidManaCostException('Unrecognized symbol type: `{symbol}` in `{symbols}`'.format(symbol=symbol, symbols=symbols))
    return cs

def generic(symbol) -> bool:
    return bool(re.match('^{digit}+$'.format(digit=DIGIT), symbol))

def variable(symbol) -> bool:
    return bool(re.match('^{x}$'.format(x=X), symbol))

def phyrexian(symbol) -> bool:
    return bool(re.match('^{color}/{modifier}$'.format(color=COLOR, modifier=MODIFIER), symbol))

def hybrid(symbol) -> bool:
    return bool(re.match('^{color}/{color}$'.format(color=COLOR), symbol))

def twobrid(symbol) -> bool:
    return bool(re.match('^2/{color}$'.format(color=COLOR), symbol))

def colored(symbol) -> bool:
    return bool(re.match('^{color}$'.format(color=COLOR), symbol))

def has_x(mana_cost) -> bool:
    return len([symbol for symbol in parse(mana_cost) if variable(symbol)]) > 0

def order(symbols: Iterable[str]) -> List[str]:
    permutations = itertools.permutations(symbols)
    return list(sorted(permutations, key=order_score)[0])

def order_score(symbols):
    symbols = [symbol for symbol in symbols if symbol != 'C']
    if not symbols:
        return 0
    score = 0
    positions = ['W', 'U', 'B', 'R', 'G']
    current = positions.index(symbols[0])
    for symbol in symbols[1:]:
        position = positions.index(symbol)
        score += position - current
        if position < current:
            score += len(positions)
        current = position
    return score * 10 + positions.index(symbols[0])

class InvalidManaCostException(ParseException):
    pass
