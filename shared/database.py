from shared import database_mysql
from shared.database_generic import GenericDatabase


def get_database(location: str) -> GenericDatabase:
    return database_mysql.MysqlDatabase(location)

def sqlescape(s, force_string: bool = False):
    if str(s).isdecimal() and not force_string:
        return s
    if isinstance(s, str):
        encodable = s.encode('utf-8', 'strict').decode('utf-8')
        if encodable.find('\x00') >= 0:
            raise Exception('NUL not allowed in SQL string.')
        return "'{escaped}'".format(escaped=encodable.replace("'", "''").replace('%', '%%'))
    raise Exception

def sqllikeescape(s: str) -> str:
    s = s.replace('%', '\\%').replace('_', '\\_')
    return sqlescape('%{s}%'.format(s=s))
