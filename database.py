import codecs, pkg_resources, re, sqlite3
import config

class Database():
  @staticmethod
  def escape(s):
    if s.isdigit():
      return s
    encodable = s.encode('utf-8', 'strict').decode('utf-8')
    if encodable.find('\x00') >= 0:
      raise Exception('NUL not allowed in SQL string.')
    return "'" + encodable.replace("'", "''") + "'"

  def __init__(self):
    db = config.Config().get('database')
    self.database = sqlite3.connect(db)
    self.database.row_factory = sqlite3.Row
    try:
      self.version()
    except sqlite3.OperationalError:
      self.setup()

  def version(self):
    return pkg_resources.parse_version(self.value("SELECT version FROM version", [], "0"))

  def execute(self, sql, args = []):
    r = self.database.execute(sql, args).fetchall()
    self.database.commit()
    return r

  def value(self, sql, args = [], default = None):
    rs = self.execute(sql, args)
    try:
      return rs[0][0]
    except IndexError:
      return default

  def setup(self):
    self.execute("CREATE TABLE version (version TEXT)")
    sql = 'CREATE TABLE card (id INTEGER PRIMARY KEY, '
    sql += ', '.join(name + ' ' + type for name, type in oracle.Oracle.properties().items()).rstrip(', ')
    sql += ')'
    self.execute(sql)
    self.execute("""CREATE TABLE card_name (
      id INTEGER PRIMARY KEY,
      card_id INTEGER NOT NULL,
      name TEXT NOT NULL,
      FOREIGN KEY(card_id) REFERENCES card(id)
    )""")
    self.execute('CREATE TABLE color (id INTEGER PRIMARY KEY, name TEXT, symbol TEXT)')
    self.execute("""CREATE TABLE card_color (
      id INTEGER PRIMARY KEY,
      card_id INTEGER NOT NULL,
      color_id INTEGER NOT NULL,
      FOREIGN KEY(card_id) REFERENCES card(id)
      FOREIGN KEY(color_id) REFERENCES color(id)
    )""")
    self.execute("""CREATE TABLE card_color_identity (
      id INTEGER PRIMARY KEY,
      card_id INTEGER NOT NULL,
      color_id INTEGER NOT NULL,
      FOREIGN KEY(card_id) REFERENCES card(id)
      FOREIGN KEY(color_id) REFERENCES color(id)
    )""")
    self.execute("""CREATE TABLE card_supertype (
      id INTEGER PRIMARY KEY,
      card_id INTEGER NOT NULL,
      supertype TEXT NOT NULL,
      FOREIGN KEY(card_id) REFERENCES card(id)
    )""")
    self.execute("""CREATE TABLE card_type (
      id INTEGER PRIMARY KEY,
      card_id INTEGER NOT NULL,
      type TEXT NOT NULL,
      FOREIGN KEY(card_id) REFERENCES card(id)
    )""")
    self.execute("""CREATE TABLE card_subtype (
      id INTEGER PRIMARY KEY,
      card_id INTEGER NOT NULL,
      subtype TEXT NOT NULL,
      FOREIGN KEY(card_id) REFERENCES card(id)
    )""")
    self.execute("""CREATE TABLE rarity (
      id INTEGER PRIMARY KEY,
      name TEXT NOT NULL
    )""")
    self.execute("""INSERT INTO color (name, symbol) VALUES
      ('White', 'W'),
      ('Blue', 'U'),
      ('Black', 'B'),
      ('Red', 'R'),
      ('Green', 'G')
    """)
    self.execute("""INSERT INTO rarity (name) VALUES
      ('Common'),
      ('Uncommon'),
      ('Rare'),
      ('Mythic Rare'),
      ('Special')
    """)

# Import last to work around circular dependency — http://effbot.org/zone/import-confusion.htm
import oracle
