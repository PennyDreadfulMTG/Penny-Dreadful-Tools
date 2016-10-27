import re

from pd_exception import ParseException

START = ''
DIGIT = '[0-9]'
COLOR = '[WURBGC]'
X = '[XYZ]'
SLASH = '/'
MODIFIER = 'P'
HALF = '[wh]'

def parse(s):
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
                raise InvalidManaCostException('Symbol must start with {digit} or {color}, `{c}` found.'.format(digit=DIGIT, color=COLOR, c=c))
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
                raise InvalidManaCostException('Digit must be followed by {digit}, {color} or {slash}, `{c}` found.'.format(digit=DIGIT, color=COLOR, slash=SLASH, c=c))
        elif mode == COLOR:
            if re.match(COLOR, c):
                tokens.append(tmp)
                tmp = c
                mode = COLOR
            elif re.match(SLASH, c):
                tmp += c
                mode = SLASH
            else:
                raise InvalidManaCostException('Color must be followed by {color} or {slash}, `{c}` found.'.format(color=COLOR, slash=SLASH, c=c))
        elif mode == SLASH:
            if re.match(COLOR, c) or re.match(MODIFIER, c):
                tokens.append(tmp + c)
                tmp = ''
                mode = START
            else:
                raise InvalidManaCostException('Slash must be followed by {color} or {modifier}, `{c}` found.'.format(color=COLOR, modifier=MODIFIER, c=c))
    if tmp:
        tokens.append(tmp)
    return tokens

def colors(symbols):
    cs = {'required': set(), 'also': set()}
    for symbol in symbols:
        if generic(symbol):
            pass
        elif phyrexian(symbol):
            cs['also'].add(symbol[0])
        elif hybrid(symbol):
            parts = symbol.split(SLASH)
            cs['also'].add(parts[0])
            cs['also'].add(parts[1])
        elif twobrid(symbol):
            parts = symbol.split(SLASH)
            cs['also'].add(parts[1])
        elif colored(symbol):
            cs['required'].add(symbol)
        else:
            raise InvalidManaCostException('Unrecognized symbol type: `{symbol}` in `{symbols}`'.format(symbol=symbol, symbols=symbols))
    return cs

def generic(symbol):
    return re.match('^({digit}*{x}*)$'.format(digit=DIGIT, x=X), symbol)

def phyrexian(symbol):
    return re.match('^{color}/{modifier}$'.format(color=COLOR, modifier=MODIFIER), symbol)

def hybrid(symbol):
    return re.match('^{color}/{color}$'.format(color=COLOR), symbol)

def twobrid(symbol):
    return re.match('^2/{color}$'.format(color=COLOR), symbol)

def colored(symbol):
    return re.match('^{color}$'.format(color=COLOR), symbol)

class InvalidManaCostException(ParseException):
    pass
