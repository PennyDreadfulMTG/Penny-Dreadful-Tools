import json
from typing import Callable, TypeVar
from typing import Optional

import redis

from . import configuration
from .container import Container
from .serialization import extra_serializer

def init() -> Optional[redis.Redis]:
    if not configuration.get_bool('redis_enabled'):
        return None
    instance = redis.Redis(
        host=configuration.get_str('redis_host'),
        port=configuration.get_int('redis_port'),
        db=configuration.get_int('redis_db'),
        )
    try:
        instance.ping()
    except redis.exceptions.ConnectionError:
        return None
    return instance

REDIS = init()


T = TypeVar('T', str, int)
GetContainerFunction = Callable[..., Optional[Container]]

def redis_cache_container(fn: GetContainerFunction) -> GetContainerFunction:
    def wrapper(*args: T, **kwargs: T) -> Optional[Container]:
        key = fn.__name__ + repr(args) + repr(kwargs)
        if REDIS is not None:
            blob = REDIS.get(key)
            if blob is not None:
                val = json.loads(blob)
                if val is not None:
                    return Container(val)
                return None
            val = fn(*args, **kwargs)
            REDIS.set(key, json.dumps(val, default=extra_serializer))
            return val
        return fn(*args, **kwargs)
    return wrapper
