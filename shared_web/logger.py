import logging
from typing import Any, List

from flask import current_app, has_app_context

def logger(): # type: ignore
    if has_app_context():
        return current_app.logger
    return logging

def fatal(*args: List[Any]) -> None:
    """Panic stations! Data is being irretrievably lost or other truly terrible things."""
    logger().fatal('\n'.join(map(str, args)))

def error(*args: Any) -> None:
    """Thing that should not happen or state that should not occur, must be fixed."""
    logger().error('\n'.join(map(str, args)))

def warning(*args: Any) -> None:
    """Potentially interesting information that will be logged in production."""
    logger().warning('\n'.join(map(str, args)))

def info(*args: Any) -> None:
    """Potentially interesting information that will not be logged in production but will be logged in dev."""
    logger().info('\n'.join(map(str, args)))

def debug(*args: Any) -> None:
    """Anything that might potentially be useful debugging an issue but not worth showing all the time, even in dev."""
    logger().debug('\n'.join(map(str, args)))
