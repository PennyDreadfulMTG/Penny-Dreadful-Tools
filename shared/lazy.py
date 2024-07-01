from collections.abc import Callable
from typing import TypeVar, cast

T = TypeVar('T')


def lazy_property(fn: Callable[[], T]) -> Callable[[], T]:
    """Decorator that makes a property lazy-evaluated."""
    attr_name = '_lazy_' + fn.__name__

    def _lazy_property() -> T:
        if not hasattr(fn, attr_name):
            setattr(fn, attr_name, fn())
        return getattr(fn, attr_name)

    return cast(Callable[[], T], _lazy_property)
