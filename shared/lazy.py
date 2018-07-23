from typing import Callable, TypeVar, cast

T = TypeVar('T')
PropertyFunction = TypeVar('PropertyFunction', bound=Callable)

def lazy_property(fn: PropertyFunction) -> PropertyFunction:
    """Decorator that makes a property lazy-evaluated.
    """
    attr_name = '_lazy_' + fn.__name__

    def _lazy_property() -> T:
        if not hasattr(fn, attr_name):
            setattr(fn, attr_name, fn())
        return getattr(fn, attr_name)
    return cast(PropertyFunction, _lazy_property)
