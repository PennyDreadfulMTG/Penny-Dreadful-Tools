from typing import List


class Token:
    values: List[str] = []

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
            if s.lower().startswith(value.lower()):
                return value
        return ''

    def __init__(self, chars):
        self.val = self.find(chars)

    def value(self):
        return self.val

    def __str__(self):
        return self.value()

    def __repr__(self):
        return self.value()


class BooleanOperator(Token):
    # Strict substrings of other operators must appear later in the list.
    values = ['AND', 'OR', 'NOT', '-']

    @classmethod
    def find(cls, chars):
        s = ''.join(chars)
        for value in cls.values:
            if s.lower().startswith(value.lower() + ' ') or (s.lower().startswith(value.lower()) and len(s) == len(value)) or (value == '-' and s.startswith('-')):
                return value
        return ''

    def value(self):
        if self.val == '-':
            return 'NOT'
        return self.val


class Criterion(Token):
    @classmethod
    def match(cls, chars):
        if not Key.match(chars):
            return False
        rest = chars[Key.length(chars):]
        if not Operator.match(rest):
            return False
        return len(rest) > 0


class Key(Token):
    # Strict substrings of other operators must appear later in the list.
    values = ['coloridentity', 'supertype', 'toughness', 'identity', 'playable', 'edition', 'subtype', 'loyalty', 'format', 'rarity', 'color', 'power', 'super', 'mana', 'text', 'type', 'cmc', 'pow', 'set', 'sub', 'tou', 'ci', 'c', 'e', 'f', 'm', 'r', 's', 'o', 't', 'is', 'p']


class Operator(Token):
    # Strict substrings of other operators must appear later in the list.
    values = ['<=', '>=', ':', '!', '<', '>', '=']


class String(Token):
    @classmethod
    def find(cls, chars):
        return chars
