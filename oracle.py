import re, types
import database, fetcher

class Oracle():
  @staticmethod
  def properties():
    return {
      'system_id': 'TEXT',
      'layout': 'TEXT',
      'name': 'TEXT',
      'mana_cost': 'TEXT',
      'cmc': 'REAL',
      'type': 'TEXT',
      'text': 'TEXT',
      'flavor': 'TEXT',
      'artist': 'TEXT',
      'number': 'TEXT',
      'power': 'TEXT',
      'toughness': 'TEXT',
      'loyalty': 'TEXT',
      'multiverse_id': 'INTEGER',
      'image_name': 'TEXT',
      'watermark': 'TEXT',
      'border': 'TEXT',
      'timeshifted': 'INTEGER',
      'hand': 'INTEGER',
      'life': 'INTEGER',
      'reserved': 'INTEGER',
      'release_date': 'INTEGER',
      'starter': 'INTEGER',
      'mci_number': 'TEXT'
    }

  @staticmethod
  def layouts():
    return ['normal', 'meld', 'split', 'phenomenon', 'token', 'vanguard', 'double-faced', 'plane', 'flip', 'scheme', 'leveler']

  def __init__(self):
    self.database = database.Database()
    self.fetcher = fetcher.Fetcher()
    current_version = self.fetcher.version()
    if current_version > self.database.version():
      print("Database update required")
      self.update_database(str(current_version))

  def search(self, query):
    sql = 'SELECT ' + (', '.join(property for property in Oracle.properties())) \
      + ' FROM card ' \
      + 'WHERE name LIKE ? ' \
      + 'ORDER BY pd_legal DESC, name'
    rs = self.database.execute(sql, ['%' + query + '%'])
    return [Card(r) for r in rs]

  def update_legality(self, legal_cards):
    self.database.execute('UPDATE card SET pd_legal = 0')
    self.database.execute('UPDATE card SET pd_legal = 1 WHERE LOWER(name) IN (' + ', '.join(database.Database.escape(name) for name in legal_cards) + ')')

  def update_database(self, new_version):
    self.database.execute('DELETE FROM version')
    self.database.execute('DELETE FROM card')
    cards = self.fetcher.all_cards()
    for name, card in cards.items():
      self.insert_card(name, card)

    self.database.database.commit()
    # mtgjson thinks that lands have a CMC of NULL so we'll work around that here.
    self.check_layouts() # Check that the hardcoded list of layouts we're about to use is still valid.
    self.database.execute("UPDATE card SET cmc = 0 WHERE cmc IS NULL AND layout IN ('normal', 'double-faced', 'flip', 'leveler', 'token', 'split')")
    self.database.execute('INSERT INTO version (version) VALUES (?)', [new_version])

  def insert_card(self, name, card):
    sql = 'INSERT INTO card ('
    sql += ', '.join(property for property in Oracle.properties())
    sql += ') VALUES ('
    sql += ', '.join('?' for prop in Oracle.properties())
    sql += ')'
    values = [card.get(self.underscore2camel(property)) for property in Oracle.properties()]
    # self.database.execute commits after each statement, which we want to
    # avoid while inserting cards
    self.database.database.execute(sql, values)
    id = self.database.value('SELECT last_insert_rowid()')
    for name in card.get('names', []):
      self.database.database.execute('INSERT INTO card_name (card_id, name) VALUES (?, ?)', [id, name])
    for color in card.get('colors', []):
      color_id = self.database.value('SELECT id FROM color WHERE name = ?', [color])
      self.database.database.execute('INSERT INTO card_color (card_id, color_id) VALUES (?, ?)', [id, color_id])
    for symbol in card.get('colorIdentity', []):
      color_id = self.database.value('SELECT id FROM color WHERE symbol = ?', [symbol])
      self.database.database.execute('INSERT INTO card_color_identity (card_id, color_id) VALUES (?, ?)', [id, color_id])
    for supertype in card.get('supertypes', []):
      self.database.database.execute('INSERT INTO card_supertype (card_id, supertype) VALUES (?, ?)', [id, supertype])
    for subtype in card.get('subtypes', []):
      self.database.database.execute('INSERT INTO card_subtype (card_id, subtype) VALUES (?, ?)', [id, subtype])

  def check_layouts(self):
    rs = self.database.execute('SELECT DISTINCT layout FROM card');
    if sorted([x[0] for x in rs]) != sorted(Oracle.layouts()):
      print("WARNING. There has been a change in layouts. The update to 0 CMC may no longer be valid.")

  def underscore2camel(self, s):
    return re.sub(r'(?!^)_([a-zA-Z])', lambda m: m.group(1).upper(), s)

class Card(types.SimpleNamespace):
  def __init__(self, params):
    [setattr(self, k, params[k]) for k in params.keys()]
