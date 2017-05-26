from shared import database_mysql, database_sqlite

def get_database(location):
    if location.lower().endswith('.sqlite'):
        return database_sqlite.SqliteDatabase(location)
    else:
        return database_mysql.MysqlDatabase(location)

def sqlescape(s) -> str:
    if str(s).isdecimal():
        return s
    encodable = s.encode('utf-8', 'strict').decode('utf-8')
    if encodable.find('\x00') >= 0:
        raise Exception('NUL not allowed in SQL string.')
    return "'{escaped}'".format(escaped=encodable.replace("'", "''"))

def sqllikeescape(s):
    s = s.replace('%', '\\%').replace('_', '\\_')
    return sqlescape('%{s}%'.format(s=s))
