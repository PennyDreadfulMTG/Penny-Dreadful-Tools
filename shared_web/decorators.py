from functools import wraps
from typing import Any, Callable

from flask import request


def fill_args(*props: str) -> Callable:
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            for arg in props:
                reqval = request.args.get(arg, None)
                if kwargs.get(arg, None) is None and reqval is not None:
                    kwargs[arg] = reqval
            return f(*args, **kwargs)
        return wrapper
    return decorator


def fill_cookies(*props: str) -> Callable:
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            for arg in props:
                reqval = request.cookies.get(arg, None)
                if kwargs.get(arg, None) is None and reqval is not None:
                    kwargs[arg] = reqval
            return f(*args, **kwargs)
        return wrapper
    return decorator


def fill_form(*props: str) -> Callable:
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            for arg in props:
                reqval = request.form.get(arg, None)
                if kwargs.get(arg, None) is None and reqval is not None:
                    kwargs[arg] = reqval
            return f(*args, **kwargs)
        return wrapper
    return decorator
