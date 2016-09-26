import collections, re
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

  def __init__(self):
    self.database = database.Database()
    self.fetcher = fetcher.Fetcher()
    current_version = self.fetcher.version()
    if current_version > self.database.version():
      self.update_database(str(current_version))

  def search(self, query):
    sql = 'SELECT ' + (', '.join(property for property in Oracle.properties())).rstrip(', ') \
      + ' FROM card ' \
      + "WHERE name LIKE ?"
    rs = self.database.execute(sql, ['%' + query + '%'])
    return [Card(*r) for r in rs]

  def update_database(self, new_version):
    self.database.execute('DELETE FROM version')
    self.database.execute('DELETE FROM card')
    cards = self.fetcher.all_cards()
    for name, card in cards.items():
      self.insert_card(name, card)
    self.database.execute('INSERT INTO version (version) VALUES (?)', [new_version])

  def insert_card(self, name, card):
    sql = 'INSERT INTO card ('
    sql += ', '.join(property for property in Oracle.properties()).rstrip(', ')
    sql += ') VALUES ('
    sql += ('?, ' * len(Oracle.properties())).rstrip(', ')
    sql += ')'
    values = [card.get(self.underscore2camel(property)) for property in Oracle.properties()]
    self.database.execute(sql, values)
    id = self.database.value('SELECT last_insert_rowid()')
    for name in card.get('names', []):
      self.database.execute('INSERT INTO card_name (card_id, name) VALUES (?, ?)', [id, name])
    for color in card.get('colors', []):
      color_id = self.database.value('SELECT id FROM color WHERE name = ?', [color])
      self.database.execute('INSERT INTO card_color (card_id, color_id) VALUES (?, ?)', [id, color_id])
    for symbol in card.get('colorIdentity', []):
      color_id = self.database.value('SELECT id FROM color WHERE symbol = ?', [symbol])
      self.database.execute('INSERT INTO card_color_identity (card_id, color_id) VALUES (?, ?)', [id, color_id])
    for supertype in card.get('supertypes', []):
      self.database.execute('INSERT INTO card_supertype (card_id, supertype) VALUES (?, ?)', [id, supertype])
    for subtype in card.get('subtypes', []):
      self.database.execute('INSERT INTO card_subtype (card_id, subtype) VALUES (?, ?)', [id, subtype])

  def underscore2camel(self, s):
    return re.sub(r'(?!^)_([a-zA-Z])', lambda m: m.group(1).upper(), s)

Card = collections.namedtuple('Card', Oracle.properties().keys())
