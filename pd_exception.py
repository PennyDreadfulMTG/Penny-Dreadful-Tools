class PDException(Exception):
    pass

class OperationalException(PDException):
    pass

class ParseException(PDException):
    pass

class InvalidDataException(PDException):
    pass

class DatabaseException(PDException):
    pass
