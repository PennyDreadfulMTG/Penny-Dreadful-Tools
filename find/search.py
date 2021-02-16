import collections
from typing import Any, Dict, Generator, Iterable, List, Optional, Union

from find.expression import Expression
from find.tokens import BooleanOperator, Criterion, Key, Operator, String, Token
from magic import card, mana, multiverse
from magic.database import db
from magic.models import Card
from shared.database import concat, sqlescape, sqllikeescape
from shared.pd_exception import ParseException


EXPECT_EXPRESSION = 'expect_expression'
EXPECT_OPERATOR = 'expect_operator'
EXPECT_TERM = 'expect_term'
QUOTED_STRING = 'quoted_string'
UNQUOTED_STRING = 'unquoted_string'

VALUE_LOOKUP: Dict[str, Dict[str, int]] = {}

def search(query: str) -> List[Card]:
    where = parse(tokenize(query))
    sql = """{base_query}
        ORDER BY pd_legal DESC, name
    """.format(base_query=multiverse.cached_base_query(where))
    rs = db().select(sql)
    return [Card(r) for r in rs]

# Cut a query string up into tokens and combine them in an Expression, recursively for subexpressisons. Or raise if string is malformed.
def tokenize(s: str) -> Expression:
    s = s.lower()
    tokens: Dict[int, List[Union[Expression, Token]]] = {0: []}
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
            elif String.match(c):
                string = [c]
                mode = UNQUOTED_STRING
            else:
                raise InvalidTokenException("Expected expression, got '{c}' at character {i} in {s}".format(c=c, i=i, s=s))
        elif mode == EXPECT_OPERATOR:
            if Operator.match(rest):
                tokens[depth].append(Operator(rest))
                mode = EXPECT_TERM
                i += Operator.length(rest) - 1
            else:
                raise InvalidTokenException("Expected operator, got '{c}' at character {i} in {s}".format(c=c, i=i, s=s))
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
            raise InvalidModeException("Bad mode '{c}' at character {i} in {s}".format(c=c, i=i, s=s))
        i += 1
    if mode == QUOTED_STRING:
        raise InvalidSearchException('Reached end of expression without finding the end of a quoted string in {s}'.format(s=s))
    if depth != 0:
        raise InvalidSearchException('Reached end of expression without finding enough closing parentheses in {s}'.format(s=s))
    return Expression(tokens[0])

# Parse an Expression into a SQL WHERE clause or raise if Expression is invalid.
def parse(expression: Expression) -> str:
    s = ''
    i = 0
    tokens = expression.tokens()
    while i < len(tokens):
        token = tokens[i]
        cls = token.__class__
        # We check the type then operate on the token, which mypy doesn't understand, so there are some `type: ignores` here.
        if cls == String:
            s += text_where('name', token.value()) # type: ignore
        elif cls == Key:
            s += parse_criterion(token, tokens[i + 1], tokens[i + 2]) # type: ignore
            i += 2
        elif cls == Expression:
            s += '({token})'.format(token=parse(token)) # type: ignore
        elif cls == BooleanOperator and i == 0 and token.value().strip() != 'NOT': # type: ignore
            raise InvalidSearchException('You cannot start a search expression with a boolean operator')
        elif cls == BooleanOperator and i == len(tokens) - 1:
            raise InvalidSearchException('You cannot end a search expression with a boolean operator')
        elif cls == BooleanOperator:
            pass
        else:
            raise InvalidTokenException("Invalid token '{token}' ({cls}) at character {i}".format(token=token, cls=cls, i=i))
        next_token = tokens[i + 1] if len(tokens) > (i + 1) else None
        next_cls = next_token.__class__
        if cls == BooleanOperator:
            s = s.rstrip(' ')
            s += ' {s} '.format(s=token.value()) # type: ignore
        elif next_cls != BooleanOperator or next_token.value() == 'NOT': # type: ignore
            s += ' AND '
        i += 1
    return s[:-len(' AND ')].replace('    ', ' ').strip()

# Parse key, operator and term tokens into a SQL boolean or raise if the tokens are invalid in combination.
def parse_criterion(key: Token, operator: Token, term: Token) -> str:
    if key.value() == 'q':
        return text_where('name', term.value())
    elif key.value() == 'color' or key.value() == 'c':
        return color_where('color', operator.value(), term.value())
    elif key.value() == 'coloridentity' or key.value() == 'identity' or key.value() == 'ci' or key.value() == 'id':
        return color_where('color_identity', operator.value(), term.value())
    elif key.value() == 'text' or key.value() == 'o':
        return text_where('text', term.value())
    elif key.value() == 'type' or key.value() == 't':
        v = 'planeswalker' if term.value() == 'pw' else term.value()
        return text_where('type_line', v)
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
    elif key.value() == 'mana' or key.value() == 'm':
        return mana_where(operator.value(), term.value())
    elif key.value() == 'is':
        return is_subquery(term.value())
    elif key.value() == 'playable' or key.value() == 'p':
        return playable_where(term.value())
    raise InvalidCriterionException

def text_where(column: str, term: str) -> str:
    q = term
    if column.endswith('name'):
        q = card.unaccent(q)
    if column == 'text':
        column = 'oracle_text'
    escaped = sqllikeescape(q)
    if column == 'oracle_text' and '~' in escaped:
        parts = ["'{text}'".format(text=text) for text in escaped.strip("'").split('~')]
        escaped = concat(intersperse(parts, 'name'))
    return '({column} LIKE {q})'.format(column=column, q=escaped)

def subtable_where(subtable: str, value: str, operator: Optional[str] = None) -> str:
    # Specialcase colorless because it has no entry in the color table.
    if (subtable == 'color' or subtable == 'color_identity') and value == 'c':
        return '(c.id NOT IN (SELECT card_id FROM card_{subtable}))'.format(subtable=subtable)
    v = value_lookup(subtable, value)
    if str(v).isdigit():
        column = '{subtable}_id'.format(subtable=subtable).replace('color_identity_id', 'color_id')
        operator = '=' if not operator else operator
    else:
        column = subtable
        v = sqllikeescape(v) # type: ignore
        operator = 'LIKE' if not operator else operator
    return '(c.id IN (SELECT card_id FROM card_{subtable} WHERE {column} {operator} {value}))'.format(subtable=subtable, column=column, operator=operator, value=v)

def math_where(column: str, operator: str, term: str) -> str:
    if operator == ':':
        operator = '='
    if operator not in ['>', '<', '=', '<=', '>=']:
        return '(1 <> 1)'
    return "({column} IS NOT NULL AND {column} <> '' AND {column} {operator} {term})".format(column=column, operator=operator, term=sqlescape(term))

def color_where(subtable: str, operator: str, term: str) -> str:
    if operator == ':' and subtable == 'color_identity':
        operator = '!' # "includes color x" doesn't really make sense in a color identity query and this matches magidex/magiccards behavior.
    colors = list(term)
    try:
        colors.remove('m')
        multicolored = True
    except ValueError:
        multicolored = False
    clause = ' OR '.join(subtable_where(subtable, color) for color in colors)
    if len(colors) > 1:
        clause = '({clause})'.format(clause=clause)
    try:
        colors.remove('c')
    except ValueError:
        pass
    if operator == '!':
        if colors:
            color_ids_clause = ' AND '.join('color_id <> {color_id}'.format(color_id=value_lookup('color', color)) for color in colors)
            clause = '({clause} AND (c.id NOT IN (SELECT card_id FROM card_{subtable} WHERE {color_ids_clause})))'.format(clause=clause, subtable=subtable, color_ids_clause=color_ids_clause)
    if not clause:
        clause = '(1 = 1)'
    if multicolored:
        clause = '({clause} AND (c.id IN (SELECT card_id FROM card_{subtable} GROUP BY card_id HAVING COUNT(card_id) > 1)))'.format(clause=clause, subtable=subtable)
    return clause

def set_where(name: str) -> str:
    return '(c.id IN (SELECT card_id FROM printing WHERE set_id IN (SELECT id FROM `set` WHERE name LIKE {name_fuzzy} OR code = {name})))'.format(name_fuzzy=sqllikeescape(name), name=sqlescape(name))

def format_where(term: str) -> str:
    if term == 'pd':
        term = 'Penny Dreadful'
    format_id = db().value('SELECT id FROM format WHERE name LIKE %s', ['{term}%%'.format(term=card.unaccent(term))])
    if format_id is None:
        raise InvalidValueException("Invalid format '{term}'".format(term=term))
    return "(c.id IN (SELECT card_id FROM card_legality WHERE format_id = {format_id} AND legality <> 'Banned'))".format(format_id=format_id)

def rarity_where(operator: str, term: str) -> str:
    rarity_id = value_lookup('rarity', term)
    if operator == ':':
        operator = '='
    if operator not in ['>', '<', '=', '<=', '>=']:
        return '(1 <> 1)'
    return "(c.id IN (SELECT card_id FROM printing WHERE rarity_id {operator} {rarity_id}))".format(operator=operator, rarity_id=rarity_id)

def mana_where(operator: str, term: str) -> str:
    term = term.upper()
    try:
        symbols = mana.parse(term) # Uppercasing input means you can't search for 1/2 or 1/2 white mana but w should match W.
        symbols = ['{{{symbol}}}'.format(symbol=symbol) for symbol in symbols]
    except mana.InvalidManaCostException:
        symbols = [term]
    if operator == ':':
        d = collections.Counter(symbols) # Group identical symbols so that UU checks for {U}{U} not just {U} twice.
        clause = ' AND '.join("mana_cost LIKE {symbol}".format(symbol=sqllikeescape(symbol * n)) for symbol, n in d.items())
    elif operator == '=':
        joined = ''.join('{symbol}'.format(symbol=symbol) for symbol in symbols)
        clause = "mana_cost = '{joined}'".format(joined=joined)
    else:
        raise InvalidTokenException('mana expects `:` or `=` not `{operator}`. Did you want cmc?'.format(operator=operator))
    return '({clause})'.format(clause=clause)

def playable_where(term: str) -> str:
    term = term.upper()
    try:
        colors = set(mana.parse(term))
    except mana.InvalidManaCostException as e:
        raise InvalidTokenException(e)
    symbols_without_curlies = colors.copy()
    # Colorless
    symbols_without_curlies.add('C')
    all_colors = ['W', 'U', 'B', 'R', 'G']
    # Phyrexian
    symbols_without_curlies.update(['{c}/P'.format(c=c) for c in all_colors])
    # Twobrid
    symbols_without_curlies.update(['2/{c}'.format(c=c) for c in all_colors])
    for color in colors:
        # Hybrid
        symbols_without_curlies.update(['{color}/{other}'.format(color=color, other=other) for other in all_colors if other != color])
        symbols_without_curlies.update(['{other}/{color}'.format(color=color, other=other) for other in all_colors if other != color])
    where = "mana_cost"
    for symbol in symbols_without_curlies:
        where = "REPLACE({where}, '{{{symbol}}}', '')".format(where=where, symbol=symbol)
    return "{where} = ''".format(where=where)

# Look up the id of a value if we have a lookup table for it.
# Raise if not found in that table.
# Return 'value' back if we don't have a a lookup table for this thing ('subtype', for example).
def value_lookup(table: str, value: str) -> Union[int, str]:
    if not VALUE_LOOKUP:
        init_value_lookup()
    if table in VALUE_LOOKUP and value in VALUE_LOOKUP[table]:
        return VALUE_LOOKUP[table][value]
    if table in VALUE_LOOKUP:
        raise InvalidValueException("Invalid value '{value}' for {table}".format(value=value, table=table))
    return value

def init_value_lookup() -> None:
    sql = """SELECT
        id,
        LOWER(name) AS name,
        LOWER(SUBSTR(name, 1, 1)) AS initial,
        LOWER(SUBSTR(TRIM(name), 1, INSTR({nameandspace}, ' ') - 1)) AS first_word,
        LOWER(REPLACE(name, ' ', '')) AS spaceless,
        LOWER({initials}) AS initials
    FROM {table}"""
    nameandspace = concat(['TRIM(name)', "' '"])
    second_initial = """CASE WHEN INSTR(name, ' ') > 0 THEN
                SUBSTR(name, INSTR(name, ' ') + 1, 1)
            ELSE
                ''
            END"""
    initials = concat(['SUBSTR(name, 1, 1)', second_initial])
    for table in ['color', 'rarity']:
        rs = db().select(sql.format(nameandspace=nameandspace, initials=initials, table=table))
        d = {}
        for row in rs:
            d[row['name']] = row['id']
            d[row['first_word']] = row['id']
            d[row['spaceless']] = row['id']
            # Special case because 'b' is black and 'u' is blue in colors.
            if table != 'color' or row['name'] != 'blue':
                d[row['initial']] = row['id']
                d[row['initials']] = row['id']
            else:
                d['u'] = row['id']
        VALUE_LOOKUP[table] = d
        if table == 'color':
            VALUE_LOOKUP['color_identity'] = d

def is_subquery(subquery_name: str) -> str:
    if subquery_name == 'split':
        return "(c.layout = 'split' OR c.layout = 'aftermath')"
    if subquery_name in multiverse.layouts().keys():
        return '(c.layout = {layout})'.format(layout=sqlescape(subquery_name))
    subqueries = {
        'gainland': 't:land o:"When ~ enters the battlefield, you gain 1 life"',
        'painland': 't:land o:"~ deals 1 damage to you."',
        'fetchland': 't:land o:"Search your library for a " (o:"land card" or o:"plains card" or o:"island card" or o:"swamp card" or o:"mountain card" or o:"forest card" or o:"gate card")',
        'slowland': """t:land o:"~ doesn't untap during your next untap step." """,
        'storageland': 'o:"storage counter"',
        'hybrid': 'mana:/2 OR mana:/W OR mana:/U OR mana:/B OR mana:/R OR mana:/G',
        'creatureland': 't:land o:"becomes a"'
    }
    subqueries['fetch'] = subqueries['fetchland']
    subqueries['refuge'] = subqueries['gainland']
    subqueries['manland'] = subqueries['creatureland']
    query = subqueries.get(subquery_name, '')
    if query == '':
        raise InvalidSearchException('Did not recognize `{subquery_name}` as a value for `is:`'.format(subquery_name=subquery_name))
    query = parse(tokenize(query))
    query = "({0})".format(query)
    return query

# pylint: disable=stop-iteration-return
def intersperse(iterable: Iterable, delimiter: str) -> Generator:
    it = iter(iterable)
    yield next(it)
    for x in it:
        yield delimiter
        yield x

class InvalidSearchException(ParseException):
    pass

class InvalidTokenException(InvalidSearchException):
    pass

class InvalidModeException(InvalidSearchException):
    pass

class InvalidValueException(InvalidSearchException):
    pass

class InvalidCriterionException(InvalidSearchException):
    pass
