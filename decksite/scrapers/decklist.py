import re

from shared.pd_exception import InvalidDataException

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
                d[part][card] = n
            except AttributeError:
                raise InvalidDataException('Unable to parse {line}'.format(line=line))
    return d
