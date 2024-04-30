class Token:
    values: list[str] = []

    @classmethod
    def match(cls, chars: str) -> bool:
        return cls.find(chars) != ''

    @classmethod
    def length(cls, chars: str) -> int:
        return len(cls.find(chars))

    @classmethod
    def find(cls, chars: str) -> str:
        s = ''.join(chars)
        for value in cls.values:
            if s.lower().startswith(value.lower()):
                return value
        return ''

    def __init__(self, chars: str) -> None:
        self.val = self.find(chars)

    def value(self) -> str:
        return self.val

    def is_regex(self) -> bool:
        return False

    def __str__(self) -> str:
        return self.value()

    def __repr__(self) -> str:
        return str(self)


class BooleanOperator(Token):
    # Strict substrings of other operators must appear later in the list.
    values = ['AND', 'OR', 'NOT', '-']

    @classmethod
    def find(cls, chars: str) -> str:
        s = ''.join(chars)
        for value in cls.values:
            if s.lower().startswith(value.lower() + ' ') or (s.lower().startswith(value.lower()) and len(s) == len(value)) or (value == '-' and s.startswith('-')):
                return value
        return ''

    def value(self) -> str:
        if self.val == '-':
            return 'NOT'
        return self.val


class Criterion(Token):
    @classmethod
    def match(cls, chars: str) -> bool:
        if not Key.match(chars):
            return False
        rest = chars[Key.length(chars):]
        if not Operator.match(rest):
            return False
        return len(rest) > 0


class Key(Token):
    # Strict substrings of other operators must appear later in the list.
    values = ['coloridentity', 'fulloracle', 'commander', 'supertype', 'toughness', 'identity', 'playable', 'produces', 'edition', 'subtype', 'loyalty', 'format', 'oracle', 'rarity', 'color', 'legal', 'power', 'super', 'mana', 'name', 'text', 'type', 'cmc', 'loy', 'pow', 'set', 'sub', 'tou', 'cid', 'not', 'ci', 'fo', 'id', 'mv', 'c', 'e', 'f', 'm', 'r', 's', 'o', 't', 'is', 'p']


class Operator(Token):
    # Strict substrings of other operators must appear later in the list.
    values = ['<=', '>=', ':', '!', '<', '>', '=']


class String(Token):
    @classmethod
    def find(cls, chars: str) -> str:
        return chars

    def __str__(self) -> str:
        return '"' + self.val + '"'


class Regex(String):
    def is_regex(self) -> bool:
        return True

    def __str__(self) -> str:
        return '/' + self.val + '/'
