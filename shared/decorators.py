import functools
from typing import Any, Callable, Dict, List

from shared.pd_exception import DatabaseException

FuncType = Callable[..., Any]

def retry_after_calling(retry_func: Callable[[], None]) -> Callable[[FuncType], FuncType]:
    def decorator(decorated_func: FuncType) -> FuncType:
        def wrapper(*args: List[Any], **kwargs: Dict[str, Any]) -> Any:
            try:
                return decorated_func(*args, **kwargs)
            except DatabaseException as e:
                print(f"Got {e} trying to call {decorated_func.__name__} so calling {retry_func.__name__} first. If this is happening on user time that's undesirable.")
                retry_func()
                try:
                    return decorated_func(*args, **kwargs)
                except DatabaseException as e:
                    print("That didn't help, giving up.")
                    raise e
        return wrapper
    return decorator

def memoize(obj: FuncType) -> FuncType:
    cache = obj.cache = {} # type: ignore

    @functools.wraps(obj)
    def memoizer(*args, **kwargs): # type: ignore
        if args not in cache:
            cache[args] = obj(*args, **kwargs)
        return cache[args]
    return memoizer
