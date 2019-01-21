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

class DatabaseMissingException(DatabaseException):
    pass

class DuplicateRowException(DatabaseException):
    pass

class DoesNotExistException(PDException):
    pass

class TooManyItemsException(PDException):
    pass

class TooFewItemsException(PDException):
    pass

class InvalidArgumentException(PDException):
    pass

class LockNotAcquiredException(DatabaseException):
    pass

class AlreadyExistsException(PDException):
    pass

class NotConfiguredException(PDException):
    pass
