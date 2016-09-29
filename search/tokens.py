class Token:
    @classmethod
    def match(cls, chars):
        return cls.find(chars) != ''

    @classmethod
    def length(cls, chars):
        return len(cls.find(chars))

    @classmethod
    def find(cls, chars):
        s = ''.join(chars)
        for value in cls.values:
            if s.startswith(value):
                return value
        return ''

    def __init__(self, chars):
        self.v = self.find(chars)

    def value(self):
        return self.v

    def __str__(self):
        return self.value()

    def __repr__(self):
        return self.value()


class BooleanOperator(Token):
    # Strict substrings of other operators must appear later in the list.
    values = ['AND', 'OR', 'NOT', '-']

    def value(self):
        if (self.v == '-'):
            return 'NOT';
        return self.v


class Criterion(Token):
    @classmethod
    def match(cls, chars):
        if (not Key.match(chars)):
            return False
        rest = chars[Key.length(chars):]
        if (not Operator.match(rest)):
            return False
        return len(rest) > 0;


class Key(Token):
    # Strict substrings of other operators must appear later in the list.
    values = ['coloridentity', 'supertype', 'toughness', 'identity', 'subtype', \
        'loyalty', 'format', 'rarity', 'color', 'power', 'super', 'mana', 'text', \
        'type', 'cmc', 'pow', 'sub', 'tou', 'ci', 'c', 'f', 'r', 'o', 't']


class Operator(Token):
    # Strict substrings of other operators must appear later in the list.
    values = ['<=', '>=', ':', '!', '<', '>', '='];


class String(Token):
    def __init__(self, string):
        self.v = string
