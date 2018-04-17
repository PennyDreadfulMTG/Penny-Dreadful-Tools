from decksite import APP
from typing import Any, List


def fatal(*args: List[Any]) -> None:
    """Panic stations! Data is being irretrievably lost or other truly terrible things."""
    APP.logger.fatal('\n'.join(map(str, args)))

def error(*args: Any) -> None:
    """Thing that should not happen or state that should not occur, must be fixed."""
    APP.logger.error('\n'.join(map(str, args)))

def warn(*args: Any) -> None:
    """Potentially interesting information that will be logged in production."""
    APP.logger.warn('\n'.join(map(str, args)))

def info(*args: Any) -> None:
    """Potentially interesting information that will not be logged in production but will be logged in dev."""
    APP.logger.info('\n'.join(map(str, args)))

def debug(*args: Any) -> None:
    """Anything that might potentially be useful debugging an issue but not worth showing all the time, even in dev."""
    APP.logger.debug('\n'.join(map(str, args)))
