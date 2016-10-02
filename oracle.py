import re

import card
import database
import fetcher

class Oracle:

    @staticmethod
    def layouts():
        return ['normal', 'meld', 'split', 'phenomenon', 'token', 'vanguard', 'double-faced', 'plane', 'flip', 'scheme', 'leveler']

    def __init__(self):
        self.card_ids = {}
        self.database = database.Database()
        current_version = fetcher.version()
        if current_version > self.database.version():
            print('Database update required')
            self.update_database(str(current_version))

    def search(self, query):
        sql = 'SELECT ' + (', '.join(property for property in card.properties())) \
            + ', alias ' \
            + ' FROM card LEFT OUTER JOIN card_alias on card.id = card_alias.card_id ' \
            + 'WHERE name LIKE ? OR alias LIKE ? ' \
            + 'ORDER BY pd_legal DESC, name'
        rs = self.database.execute(sql, ['%' + query + '%', '%' + query + '%'])
        return [card.Card(r) for r in rs]

    def update_legality(self, legal_cards):
        self.database.execute('UPDATE card SET pd_legal = 0')
        self.database.execute('UPDATE card SET pd_legal = 1 WHERE LOWER(name) IN (' + ', '.join(database.Database.escape(name) for name in legal_cards) + ')')

    def update_database(self, new_version):
        self.database.execute('DELETE FROM version')
        cards = fetcher.all_cards()
        for name, c in cards.items():
            self.insert_card(c)
        sets = fetcher.all_sets()
        for name, s in sets.items():
            self.insert_set(s)
        self.database.database.commit()
        # mtgjson thinks that lands have a CMC of NULL so we'll work around that here.
        self.check_layouts() # Check that the hardcoded list of layouts we're about to use is still valid.
        self.database.execute("UPDATE card SET cmc = 0 WHERE cmc IS NULL AND layout IN ('normal', 'double-faced', 'flip', 'leveler', 'token', 'split')")
        rs = self.database.execute('SELECT id, name FROM rarity')
        for row in rs:
            self.database.execute('UPDATE printing SET rarity_id = ? WHERE rarity = ?', [row['id'], row['name']])
        aliases = fetcher.card_aliases()
        for alias, name in aliases:
            card_id = self.database.value('SELECT id FROM card WHERE name = ?', [name])
            if card_id is not None:
                self.database.execute('INSERT INTO card_alias (card_id, alias) VALUES (?, ?)', [card_id, alias])
            else:
                print("no match for " + name)
        self.database.execute('INSERT INTO version (version) VALUES (?)', [new_version])

    def insert_card(self, c):
        sql = 'INSERT INTO card ('
        sql += ', '.join(prop for prop in card.properties())
        sql += ') VALUES ('
        sql += ', '.join('?' for prop in card.properties())
        sql += ')'
        values = [c.get(underscore2camel(prop)) for prop in card.properties()]
        # self.database.execute commits after each statement, which we want to
        # avoid while inserting cards
        self.database.database.execute(sql, values)
        card_id = self.database.value('SELECT last_insert_rowid()')
        self.card_ids[c.get('name')] = card_id
        for name in c.get('names', []):
            self.database.database.execute('INSERT INTO card_name (card_id, name) VALUES (?, ?)', [card_id, name])
        for color in c.get('colors', []):
            color_id = self.database.value('SELECT id FROM color WHERE name = ?', [color])
            self.database.database.execute('INSERT INTO card_color (card_id, color_id) VALUES (?, ?)', [card_id, color_id])
        for symbol in c.get('colorIdentity', []):
            color_id = self.database.value('SELECT id FROM color WHERE symbol = ?', [symbol])
            self.database.database.execute('INSERT INTO card_color_identity (card_id, color_id) VALUES (?, ?)', [card_id, color_id])
        for supertype in c.get('supertypes', []):
            self.database.database.execute('INSERT INTO card_supertype (card_id, supertype) VALUES (?, ?)', [card_id, supertype])
        for subtype in c.get('subtypes', []):
            self.database.database.execute('INSERT INTO card_subtype (card_id, subtype) VALUES (?, ?)', [card_id, subtype])

    def insert_set(self, s):
        sql = 'INSERT INTO `set` ('
        sql += ', '.join(prop for prop in card.set_properties())
        sql += ') VALUES ('
        sql += ', '.join('?' for prop in card.set_properties())
        sql += ')'
        values = [s.get(underscore2camel(prop)) for prop in card.set_properties()]
        # self.database.execute commits after each statement, which we want to
        # avoid while inserting sets
        self.database.database.execute(sql, values)
        set_id = self.database.value('SELECT last_insert_rowid()')
        for c in s.get('cards', []):
            card_id = self.card_ids[c.get('name')]
            sql = 'INSERT INTO printing (card_id, set_id, '
            sql += ', '.join(prop for prop in card.printing_properties())
            sql += ') VALUES (?, ?, '
            sql += ', '.join('?' for prop in card.printing_properties())
            sql += ')'
            values = [card_id, set_id] + [c.get(underscore2camel(prop)) for prop in card.printing_properties()]
            self.database.database.execute(sql, values)

    def check_layouts(self):
        rs = self.database.execute('SELECT DISTINCT layout FROM card')
        if sorted([x[0] for x in rs]) != sorted(Oracle.layouts()):
            print('WARNING. There has been a change in layouts. The update to 0 CMC may no longer be valid.')

def underscore2camel(s):
    return re.sub(r'(?!^)_([a-zA-Z])', lambda m: m.group(1).upper(), s)
