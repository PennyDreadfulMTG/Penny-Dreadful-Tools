# make_stub_files: Sun 31 Dec 2017 at 16:46:32
from shared.database_generic import GenericDatabase 

def get_database(location: str) -> GenericDatabase: ...
    #   0: return database_sqlite.SqliteDatabase(location)
    # ? 0: return database_sqlite.SqliteDatabase(location)
    #   1: return database_mysql.MysqlDatabase(location)
    # ? 1: return database_mysql.MysqlDatabase(location)
def sqlescape(s: str, force_string: bool) -> str: ...
    #   0: return s
    # ? 0: return s
    #   1: return "'{escaped}'".format(escaped=encodable.replace("'","''").replace('%','%%'))
    # ? 1: return str.format(escaped=encodable.replace(str, str).replace(str, str))
def sqllikeescape(s: str) -> str: ...
    #   0: return sqlescape('%{s}%'.format(s=s))
    # ? 0: return sqlescape(str.format(s=s))
