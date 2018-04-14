from shared.database_mysql import MysqlDatabase
from shared.pd_exception import InvalidArgumentException


def get_database(location: str) -> MysqlDatabase:
    return MysqlDatabase(location)

def sqlescape(s, force_string: bool = False, backslashed_escaped=False):
    if str(s).isdecimal() and not force_string:
        return s
    if isinstance(s, str):
        encodable = s.encode('utf-8', 'strict').decode('utf-8')
        if encodable.find('\x00') >= 0:
            raise Exception('NUL not allowed in SQL string.')
        if not backslashed_escaped:
            encodable = encodable.replace("\\", "\\\\")
        return "'{escaped}'".format(escaped=encodable.replace("'", "''").replace('%', '%%'))
    raise InvalidArgumentException('Cannot sqlescape `{s}`'.format(s=s))

def sqllikeescape(s: str) -> str:
    s = s.replace("\\", "\\\\").replace('%', '\\%').replace('_', '\\_')
    return sqlescape('%{s}%'.format(s=s), backslashed_escaped=True)
