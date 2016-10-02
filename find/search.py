import re

import card
import database

from find.expression import Expression
from find.tokens import BooleanOperator, Criterion, Key, Operator, String

EXPECT_EXPRESSION = 'expect_expression'
EXPECT_OPERATOR = 'expect_operator'
EXPECT_TERM = 'expect_term'
QUOTED_STRING = 'quoted_string'
UNQUOTED_STRING = 'unquoted_string'

def search(query):
    where_clause = parse(tokenize(query))
    sql = 'SELECT ' + (', '.join(property for property in card.properties())) \
        + ' FROM card ' \
        + 'WHERE ' + where_clause \
        + ' ORDER BY pd_legal DESC, name'
    print(sql)
    rs = database.Database().execute(sql)
    return [card.Card(r) for r in rs]

def tokenize(s):
    tokens = {0: []}
    chars = list(s)
    chars.append(' ')
    depth = 0
    i = 0
    mode = EXPECT_EXPRESSION
    while i < len(chars):
        c = chars[i]
        rest = s[i:]
        if mode == EXPECT_EXPRESSION:
            if c == '(':
                depth += 1
                tokens[depth] = []
            elif c == ')':
                expression = Expression(tokens[depth])
                del tokens[depth]
                depth -= 1
                tokens[depth].append(expression)
            elif Criterion.match(rest):
                tokens[depth].append(Key(rest))
                mode = EXPECT_OPERATOR
                i += Key.length(rest) - 1
            elif BooleanOperator.match(rest):
                tokens[depth].append(BooleanOperator(rest))
                mode = EXPECT_EXPRESSION
                i += BooleanOperator.length(rest) - 1
            elif c == '"':
                string = []
                mode = QUOTED_STRING
            elif c == ' ':
                pass # noop
            elif re.match('[A-Za-z0-9]', c):
                string = [c]
                mode = UNQUOTED_STRING
            else:
                raise InvalidTokenException("Expected expression, got '{c}' at {i} in {s}".format(c=c, i=i, s=s))
        elif mode == EXPECT_OPERATOR:
            if Operator.match(rest):
                tokens[depth].append(Operator(rest))
                mode = EXPECT_TERM
                i += Operator.length(rest) - 1
            else:
                raise InvalidTokenException("Expected operator, got '{c}' at {i} in {s}".format(c=c, i=i, s=s))
        elif mode == EXPECT_TERM:
            if c == '"':
                string = []
                mode = QUOTED_STRING
            else:
                string = [c]
                mode = UNQUOTED_STRING
        elif mode == QUOTED_STRING:
            if c == '"':
                tokens[depth].append(String(''.join(string)))
                mode = EXPECT_EXPRESSION
            else:
                string.append(c)
        elif mode == UNQUOTED_STRING:
            if c == ' ':
                tokens[depth].append(String(''.join(string)))
                mode = EXPECT_EXPRESSION
            elif c == ')':
                tokens[depth].append(String(''.join(string)))
                mode = EXPECT_EXPRESSION
                i -= 1
            else:
                string.append(c)
        else:
            raise InvalidModeException("Bad mode '{c}' at {i} in {s}".format(c=c, i=i, s=s))
        i += 1
    return Expression(tokens[0])

def parse(expression):
    s = ''
    i = 0
    tokens = expression.tokens()
    while i < len(tokens):
        token = tokens[i]
        cls = token.__class__
        if cls == String:
            s += where(['name', 'type', 'text'], token.value())
        elif cls == Key:
            s += parse_criterion(token, tokens[i + 1], tokens[i + 2])
            i += 2
        elif cls == Expression:
            s += '({token})'.format(token=parse(token))
        elif cls == BooleanOperator:
            pass
        else:
            raise InvalidTokenException("Invalid token '{token}' ({cls}) at {i}".format(token=token, cls=cls, i=i))
        next_token = tokens[i + 1] if len(tokens) > (i + 1) else None
        next_cls = next_token.__class__
        if cls == BooleanOperator:
            s = s.rstrip(' ')
            s += ' {s} '.format(s=token.value())
        elif next_cls != BooleanOperator or next_token.value() == 'NOT':
            s += ' AND '
        i += 1
    return s[:-len(' AND ')].replace('    ', ' ').strip()

def parse_criterion(key, operator, term):
    if key.value() == 'q':
        return where(['name', 'type', 'text'], term.value())
    elif key.value() == 'color' or key.value() == 'c':
        return subtable_where('color', term.value())
    elif key.value() == 'coloridentity' or key.value() == 'identity' or key.value() == 'ci':
        return subtable_where('color_identity', term.value())
    elif key.value() == 'text' or key.value() == 'o':
        return where(['text'], term.value())
    elif key.value() == 'type' or key.value() == 't':
        return where(['type'], term.value())
    elif key.value() == 'mana':
        return where(['cost'], term.value(), True)
    elif key.value() == 'power' or key.value() == 'pow':
        return math_where('power', operator.value(), term.value())
    elif key.value() == 'toughness' or key.value() == 'tou':
        return math_where('toughness', operator.value(), term.value())
    elif key.value() == 'cmc':
        return math_where('cmc', operator.value(), term.value())
    elif key.value() == 'loyalty':
        return math_where('loyalty', operator.value(), term.value())
    elif key.value() == 'supertype' or key.value() == 'super':
        return subtable_where('supertype', term.value())
    elif key.value() == 'subtype' or key.value() == 'sub':
        return subtable_where('subtype', term.value())
    elif key.value() == 'edition' or key.value() == 'set' or key.value() == 'e' or key.value() == 's':
        return set_where(term.value())
    elif key.value() == 'format' or key.value() == 'f':
        return format_where(term.value())
    elif key.value() == 'rarity' or key.value() == 'r':
        return rarity_where(operator.value(), term.value())

def where(keys, term, exact_match=False):
    q = term if exact_match else '%' + term + '%'
    subsequent = False
    s = '('
    for column in keys:
        if subsequent:
            s += ' OR '
        s += '{column} LIKE {q}'.format(column=column, q=database.Database.escape(q))
        subsequent = True
    s += ')'
    return s

def subtable_where(subtable, value):
    # Specialcase colorless because it has no entry in the color table.
    if subtable == 'color' and value == 'c':
        return '(id NOT IN (SELECT card_id FROM card_color))'
    v = value_lookup(subtable, value)
    if str(v).isdigit():
        column = '{subtable}_id'.format(subtable=subtable).replace('color_identity', 'color')
        operator = '='
    else:
        column = subtable
        v = database.Database.escape('%{v}%'.format(v=v))
        operator = 'LIKE'
    return '(id IN (SELECT card_id FROM card_{subtable} WHERE {column} {operator} {value}))'.format(subtable=subtable, column=column, operator=operator, value=v)

def math_where(column, operator, term):
    if operator == ':':
        operator = '='
    if operator not in ['>', '<', '=', '<=', '>=']:
        return '(FALSE)'
    return "({column} IS NOT NULL AND {column} <> '' AND CAST({column} AS REAL) {operator} {term})".format(column=column, operator=operator, term=database.Database.escape(term))

def set_where(name):
    name_fuzzy = '%{name}%'.format(name=name)
    return '(id IN (SELECT card_id FROM printing WHERE set_id IN (SELECT id FROM `set` WHERE name LIKE {name_fuzzy} OR code = {name} COLLATE NOCASE)))'.format(name_fuzzy=database.Database.escape(name_fuzzy), name=database.Database.escape(name))

def format_where(term):
    if term in ['pennydreadful', 'pd']:
        return '(pd_legal = 1)'
    else:
        raise InvalidValueException('{term} is not supported in format queries', term=term)

def rarity_where(operator, term):
    rarity_id = value_lookup('rarity', term)
    if operator == ':':
        operator = '='
    if operator not in ['>', '<', '=', '<=', '>=']:
        return '(FALSE)'
    return "(id IN (SELECT card_id FROM printing WHERE rarity_id {operator} {rarity_id}))".format(operator=operator, rarity_id=rarity_id)

def value_lookup(table, value):
    colors = {
        'w': 1,
        'white': 1,
        'u': 2,
        'blue': 2,
        'b': 3,
        'black': 3,
        'r': 4,
        'red': 4,
        'g': 5,
        'green': 5
    }
    replacements = {
        'color': colors,
        'color_identity': colors,
        'rarity': {
            'basic land': 1,
            'basicland': 1,
            'basic': 1,
            'land': 1,
            'bl': 1,
            'b': 1,
            'l': 1,
            'common': 2,
            'c': 2,
            'uncommon': 3,
            'u': 3,
            'rare': 4,
            'r': 4,
            'mythic rare': 5,
            'mythicrare': 5,
            'mythic': 5,
            'mr': 5,
            'm': 5
        }
    }
    if table in replacements and value.lower() in replacements[table]:
        return replacements[table][value.lower()]
    return value

class InvalidSearchException(Exception):
    pass

class InvalidTokenException(InvalidSearchException):
    pass

class InvalidModeException(InvalidSearchException):
    pass

class InvalidValueException(InvalidSearchException):
    pass
