import apsw

from magic import card
from shared import configuration
from shared.database_generic import GenericDatabase
from shared.pd_exception import DatabaseException

class Database(GenericDatabase):
    def __init__(self, location):
        try:
            self.connection = apsw.Connection(location)
            self.connection.setrowtrace(row_factory)
            self.connection.enableloadextension(True)
            self.connection.loadextension(configuration.get('spellfix'))
            self.connection.createscalarfunction('unaccent', card.unaccent, 1)
            self.cursor = self.connection.cursor()
        except apsw.Error as e:
            raise DatabaseException('Failed to initialized database in `{location}`'.format(location=location)) from e

    def execute(self, sql, args=None):
        if args is None:
            args = []
        try:
            return self.cursor.execute(sql, args).fetchall()
        except apsw.Error as e:
            # Quick fix for league bugs
            if "cannot start a transaction within a transaction" in str(e):
                self.execute("ROLLBACK")
                if sql == "BEGIN TRANSACTION":
                    return self.cursor.execute(sql, args).fetchall()
            raise DatabaseException('Failed to execute `{sql}` because of `{e}`'.format(sql=sql, e=e)) from e

def row_factory(cursor, row):
    columns = [t[0] for t in cursor.getdescription()]
    return dict(zip(columns, row))
