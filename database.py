import pkg_resources, sqlite3
import config

class Database:
    # Bump this if you modify the schema.
    schema_version = 1

    @staticmethod
    def escape(s):
        if s.isdecimal():
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
            if (self.db_version() < self.schema_version):
                self.droptables()
                self.setup()
        except sqlite3.OperationalError:
            self.setup()

    def version(self):
        return pkg_resources.parse_version(self.value("SELECT version FROM version", [], "0"))

    def db_version(self):
        return self.value("SELECT version FROM db_version", [], "0")


    def execute(self, sql, args = None):
        if args is None:
            args = []
        r = self.database.execute(sql, args).fetchall()
        self.database.commit()
        return r

    def value(self, sql, args = None, default = None):
        rs = self.database.execute(sql, args).fetchone()
        if rs is None:
            return default
        elif len(rs) <= 0:
            return default
        else:
            return rs[0]

    def setup(self):
        self.execute("CREATE TABLE IF NOT EXISTS db_version (version INTEGER)")
        self.execute("INSERT INTO db_version (version) VALUES ({0})".format(self.schema_version))
        self.execute("CREATE TABLE IF NOT EXISTS version (version TEXT)")
        sql = 'CREATE TABLE card (id INTEGER PRIMARY KEY, pd_legal INTEGER, '
        sql += ', '.join(name + ' ' + type for name, type in oracle.Oracle.properties().items())
        sql += ')'
        self.execute(sql)
        self.execute("""CREATE TABLE IF NOT EXISTS card_name (
            id INTEGER PRIMARY KEY,
            card_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            FOREIGN KEY(card_id) REFERENCES card(id)
        )""")
        self.execute('CREATE TABLE IF NOT EXISTS color (id INTEGER PRIMARY KEY, name TEXT, symbol TEXT)')
        self.execute("""CREATE TABLE IF NOT EXISTS card_color (
            id INTEGER PRIMARY KEY,
            card_id INTEGER NOT NULL,
            color_id INTEGER NOT NULL,
            FOREIGN KEY(card_id) REFERENCES card(id)
            FOREIGN KEY(color_id) REFERENCES color(id)
        )""")
        self.execute("""CREATE TABLE IF NOT EXISTS card_color_identity (
            id INTEGER PRIMARY KEY,
            card_id INTEGER NOT NULL,
            color_id INTEGER NOT NULL,
            FOREIGN KEY(card_id) REFERENCES card(id)
            FOREIGN KEY(color_id) REFERENCES color(id)
        )""")
        self.execute("""CREATE TABLE IF NOT EXISTS card_supertype (
            id INTEGER PRIMARY KEY,
            card_id INTEGER NOT NULL,
            supertype TEXT NOT NULL,
            FOREIGN KEY(card_id) REFERENCES card(id)
        )""")
        self.execute("""CREATE TABLE IF NOT EXISTS card_type (
            id INTEGER PRIMARY KEY,
            card_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            FOREIGN KEY(card_id) REFERENCES card(id)
        )""")
        self.execute("""CREATE TABLE IF NOT EXISTS card_subtype (
            id INTEGER PRIMARY KEY,
            card_id INTEGER NOT NULL,
            subtype TEXT NOT NULL,
            FOREIGN KEY(card_id) REFERENCES card(id)
        )""")
        self.execute("""CREATE TABLE IF NOT EXISTS rarity (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        )""")
        self.execute("DELETE FROM color")
        self.execute("""INSERT INTO color (name, symbol) VALUES
            ('White', 'W'),
            ('Blue', 'U'),
            ('Black', 'B'),
            ('Red', 'R'),
            ('Green', 'G')
        """)
        self.execute("DELETE FROM rarity")
        self.execute("""INSERT INTO rarity (name) VALUES
            ('Common'),
            ('Uncommon'),
            ('Rare'),
            ('Mythic Rare'),
            ('Special')
        """)

    # Drop All Tables, so we can reinit
    def droptables(self):
        self.execute("DROP TABLE IF EXISTS card")
        self.execute("DROP TABLE IF EXISTS card_color")
        self.execute("DROP TABLE IF EXISTS card_color_identity")
        self.execute("DROP TABLE IF EXISTS card_name")
        self.execute("DROP TABLE IF EXISTS card_subtype")
        self.execute("DROP TABLE IF EXISTS card_supertype")
        self.execute("DROP TABLE IF EXISTS card_type")
        self.execute("DROP TABLE IF EXISTS color")
        self.execute("DROP TABLE IF EXISTS rarity")
        self.execute("DROP TABLE IF EXISTS version")
        self.execute("DROP TABLE IF EXISTS db_version")

# Import last to work around circular dependency � http://effbot.org/zone/import-confusion.htm
import oracle
