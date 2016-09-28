import re, sys

import oracle, database, search

EXPECT_EXPRESSION = 'expect_expression'
EXPECT_OPERATOR = 'expect_operator'
EXPECT_TERM = 'expect_term'
QUOTED_STRING = 'quoted_string'
UNQUOTED_STRING = 'unquoted_string'

class Search:
  def __init__(self, query):
    self.query = query

  def fetchall(self):
    sql = 'SELECT ' + (', '.join(property for property in oracle.Oracle.properties())) \
      + ' FROM card ' \
      + 'WHERE ' + self.where_clause() \
      + ' ORDER BY pd_legal DESC'
    print(sql)
    rs = database.Database().execute(sql)
    return [oracle.Card(r) for r in rs]

  def where_clause(self):
    return self.parse(self.tokenize(self.query))

  def tokenize(self, s):
    tokens = { 0: [] }
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
          expression = search.Expression(tokens[depth])
          del tokens[depth]
          depth -= 1
          tokens[depth].append(expression)
        elif search.Criterion.match(rest):
          tokens[depth].append(search.Key(rest))
          mode = EXPECT_OPERATOR
          i += search.Key.length(rest) - 1
        elif search.BooleanOperator.match(rest):
          tokens[depth].append(search.BooleanOperator(rest))
          mode = EXPECT_EXPRESSION
          i += search.BooleanOperator.length(rest) - 1
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
        if search.Operator.match(rest):
          tokens[depth].append(search.Operator(rest))
          mode = EXPECT_TERM
          i += search.Operator.length(rest) - 1
        else:
          raise InvalidTokenException("Expected operator, got '{c}' at {i} in {s}".format(c=c, i=i, s=s))
      elif mode == EXPECT_TERM:
        if c == '"':
          string = []
          mode = QUOTED_STRING
        else:
          string = [c]
          mode = UNQUOTED_STRING
      elif (mode == QUOTED_STRING):
        if c == '"':
          tokens[depth].append(search.String(''.join(string)))
          mode = EXPECT_EXPRESSION
        else:
          string.append(c)
      elif mode == UNQUOTED_STRING:
        if c == ' ':
          tokens[depth].append(search.String(''.join(string)))
          mode = EXPECT_EXPRESSION
        elif c == ')':
          tokens[depth].append(search.String(''.join(string)))
          mode = EXPECT_EXPRESSION
          i -= 1
        else:
          string.append(c)
      else:
        raise InvalidModeException("Bad mode '{c}' at {i} in {s}".format(c=c, i=i, s=s))
      i += 1
    return search.Expression(tokens[0])

  def parse(self, expression):
    where = ''
    i = 0
    tokens = expression.tokens()
    while i < len(tokens):
      token = tokens[i]
      cls = token.__class__
      if cls == search.String:
        where += self.where(['name', 'type', 'text'], token.value())
      elif cls == search.Key:
        where += self.parse_criterion(token, tokens[i + 1], tokens[i + 2])
        i += 2
      elif cls == search.Expression:
        where += '({token})'.format(token=self.parse(token))
      elif cls == search.BooleanOperator:
        pass
      else:
        raise InvalidTokenException("Invalid token '{token}' ({cls}) at {i}".format(token=token, cls=cls, i=i))
      next_token = tokens[i + 1] if len(tokens) > (i + 1) else None
      next_cls = next_token.__class__
      if cls == search.BooleanOperator:
        where += ' {s} '.format(s=token.value())
      elif next_cls != search.BooleanOperator or next_token.value() == 'NOT':
        where += ' AND '
      i += 1
    return where[:-len(' AND ')].replace('  ', ' ').strip()

  def parse_criterion(self, key, operator, term):
    if key.value() == 'q':
      return self.where(['name', 'type', 'text'], term.value())
    elif key.value() == 'color' or key.value() == 'c':
      return self.color_where(term.value())
    elif key.value() == 'rarity' or key.value() == 'r':
      return self.where(['rarity'], self.rarity_replace(term.value()), True)
    elif key.value() == 'text' or key.value() == 'o':
      return self.where(['text'], term.value())
    elif key.value() == 'type' or key.value() == 't':
      return self.where(['type'], term.value())
    elif key.value() == 'mana':
      return self.where(['cost'], term.value(), True)
    elif key.value() == 'power' or key.value() == 'pow':
      return self.math_where('power', operator.value(), term.value())
    elif key.value() == 'toughness' or key.value() == 'tou':
      return self.math_where('toughness', operator.value(), term.value())
    elif key.value() == 'cmc':
      return self.math_where('cmc', operator.value(), term.value())
    elif key.value() == 'loyalty':
      return self.math_where('loyalty', operator.value(), term.value())

  def where(self, keys, term, exact_match = False):
    q = term if exact_match else '%' + term + '%'
    subsequent = False
    where = "("
    for column in keys:
      if subsequent:
        where += ' OR '
      where += column + " LIKE " + database.Database.escape(q)
      subsequent = True
    where += ")"
    return where

  def color_where(self, value):
    if value == 'c':
      return '(id NOT IN (SELECT card_id FROM card_color))'
    return '(id IN (SELECT card_id FROM card_color WHERE color_id = {color_id}))'.format(color_id=self.color_replace(value))

  def math_where(self, column, operator, term):
    if not operator in ['>', '<', '=', '<=', '>=']:
      return 'FALSE'
    return "({column} IS NOT NULL AND {column} <> '' AND CAST({column} AS REAL) {operator} {term})".format(column=column, operator=operator, term=database.Database.escape(term))

  def color_replace(self, color):
    replacements = {
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
    if color.lower() in replacements:
      return replacements[color.lower()]
    return color

  def rarity_replace(self, rarity):
    replacements = {
        'common': 'C',
        'uncommon': 'U',
        'rare': 'R',
        'mythic': 'M',
        'mythicrare': 'M',
        'mythic rare': 'M'
    }
    if rarity.lower() in replacements:
      return replacements[rarity.lower()]
    return rarity

class InvalidTokenException(Exception):
  pass

class InvalidModeException(Exception):
  pass
