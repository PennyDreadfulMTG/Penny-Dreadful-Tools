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
        self.format_ids = {}
        self.database = database.Database()
        current_version = fetcher.version()
        if current_version > self.database.version():
            print('Database update required')
            self.update_database(str(current_version))
        aliases = fetcher.card_aliases()
        if self.database.alias_count() != len(aliases):
            print('Card alias update required')
            self.update_card_aliases(aliases)

    def search(self, query):
        sql = 'SELECT card.id, ' + (', '.join(property for property in card.properties())) \
            + ', alias ' \
            + ' FROM card LEFT OUTER JOIN card_alias on card.id = card_alias.card_id ' \
            + 'WHERE name LIKE ? OR alias LIKE ? ' \
            + 'ORDER BY pd_legal DESC, name'
        rs = self.database.execute(sql, ['%' + query + '%', '%' + query + '%'])
        return [card.Card(r) for r in rs]

    def get_legal_cards(self, force=False):
        new_list = fetcher.legal_cards(force)
        if new_list == ['']:
            new_list = [card.Card(r).name.lower() for r in self.database.execute('SELECT name FROM card WHERE pd_legal = 1')]
            if len(new_list) == 0:
                new_list = fetcher.legal_cards(force=True)
        else:
            self.database.execute('UPDATE card SET pd_legal = 0')
            self.database.execute('UPDATE card SET pd_legal = 1 WHERE LOWER(name) IN (' + ', '.join(database.escape(name) for name in new_list) + ')')
        return new_list

    def update_database(self, new_version):
        self.database.execute('DELETE FROM version')
        cards = fetcher.all_cards()
        for _, c in cards.items():
            self.insert_card(c)
        sets = fetcher.all_sets()
        for _, s in sets.items():
            self.insert_set(s)
        self.database.database.commit()
        # mtgjson thinks that lands have a CMC of NULL so we'll work around that here.
        self.check_layouts() # Check that the hardcoded list of layouts we're about to use is still valid.
        self.database.execute("UPDATE card SET cmc = 0 WHERE cmc IS NULL AND layout IN ('normal', 'double-faced', 'flip', 'leveler', 'token', 'split')")
        rs = self.database.execute('SELECT id, name FROM rarity')
        for row in rs:
            self.database.execute('UPDATE printing SET rarity_id = ? WHERE rarity = ?', [row['id'], row['name']])
        self.update_card_aliases(fetcher.card_aliases())
        self.database.execute('INSERT INTO version (version) VALUES (?)', [new_version])

    def update_card_aliases(self, aliases):
        self.database.execute('DELETE FROM card_alias', [])
        for alias, name in aliases:
            card_id = self.database.value('SELECT id FROM card WHERE name = ?', [name])
            if card_id is not None:
                self.database.execute('INSERT INTO card_alias (card_id, alias) VALUES (?, ?)', [card_id, alias])
            else:
                print("no card found named " + name + " for alias " + alias)

    def insert_card(self, c):
        sql = 'INSERT INTO card ('
        sql += ', '.join(prop for prop in card.properties())
        sql += ') VALUES ('
        sql += ', '.join('?' for prop in card.properties())
        sql += ')'
        values = [c.get(database2json(prop)) for prop in card.properties()]
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
        for info in c.get('legalities', []):
            format_id = self.format_id(info['format'], True)
            self.database.database.execute('INSERT INTO card_legality (card_id, format_id, legality) VALUES (?, ?, ?)', [card_id, format_id, info['legality']])

    def insert_set(self, s) -> None:
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

    def format_id(self, name, allow_create=False):
        if len(self.format_ids) == 0:
            rs = self.database.execute('SELECT id, name FROM format')
            for row in rs:
                self.format_ids[row['name']] = row['id']
        if name not in self.format_ids.keys() and allow_create:
            self.database.execute('INSERT INTO format (name) VALUES (?)', [name])
            self.format_ids[name] = self.database.value('SELECT last_insert_rowid()')
        if name not in self.format_ids.keys():
            return None
        return self.format_ids[name]

    def check_layouts(self):
        rs = self.database.execute('SELECT DISTINCT layout FROM card')
        if sorted([x[0] for x in rs]) != sorted(Oracle.layouts()):
            print('WARNING. There has been a change in layouts. The update to 0 CMC may no longer be valid.')

    def get_printings(self, generalized_card: card.Card):
        sql = 'SELECT ' + (', '.join(property for property in card.printing_properties())) \
            + ' FROM printing ' \
            + ' WHERE card_id = ? ' \

        rs = self.database.execute(sql, [generalized_card.id])
        return [card.Printing(r) for r in rs]

def database2json(propname: str) -> str:
    #if propname == "system_id":
    #    propname = "id"
    return underscore2camel(propname)

def underscore2camel(s):
    return re.sub(r'(?!^)_([a-zA-Z])', lambda m: m.group(1).upper(), s)
