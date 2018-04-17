from decksite import APP


def fatal(*args):
    """Panic stations! Data is being irretrievably lost or other truly terrible things."""
    APP.logger.fatal(*args)

def error(*args):
    """Thing that should not happen or state that should not occur, must be fixed."""
    APP.logger.error(*args)

def warn(*args):
    """Potentially interesting information that will be logged in production."""
    APP.logger.warn(*args)

def info(*args):
    """Potentially interesting information that will not be logged in production but will be logged in dev."""
    APP.logger.info(*args)

def debug(*args):
    """Anything that might potentially be useful debugging an issue but not worth showing all the time, even in dev."""
    APP.logger.debug(*args)
