import re

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
            elif re.match(MODIFIER, c):
                tokens.append(tmp + c)
                tmp = ''
                mode = START
            else:
                raise InvalidManaCostException('Color must be followed by {color}, {slash} or {modifier}, `{c}` found.'.format(color=COLOR, slash=SLASH, modifier=MODIFIER, c=c))
        elif mode == SLASH:
            if re.match(COLOR, c):
                tokens.append(tmp +c)
                tmp = ''
                mode = START
            else:
                raise InvalidManaCostException('Slash must be followed by {color}, `{c}` found.'.format(color=COLOR, c=c))
    if tmp:
        tokens.append(tmp)
    return tokens

class InvalidManaCostException(Exception):
    pass
