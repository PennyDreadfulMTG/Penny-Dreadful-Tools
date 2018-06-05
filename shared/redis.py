import json
from typing import Optional, TypeVar, List, Any

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

def get_container(key: str) -> Optional[Container]:
    if REDIS is not None:
        blob = REDIS.get(key)
        if blob is not None:
            val = json.loads(blob)
            if val is not None:
                return Container(val)
    return None

def get_list(key: str) -> Optional[List[str]]:
    if REDIS is not None:
        blob = REDIS.get(key)
        if blob is not None:
            val = json.loads(blob)
            return val
    return None

T = TypeVar('T', dict, list, str, covariant=True)

def store(key: str, val: T, **kwargs: Any) -> T:
    if REDIS is not None:
        REDIS.set(key, json.dumps(val, default=extra_serializer), **kwargs)
    return val

