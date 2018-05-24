import redis
from typing import Optional

from . import configuration

def init() -> Optional[redis.Redis]:
    if not configuration.get_bool('redis_enabled'):
        return None
    instance = redis.Redis(
        host=configuration.get_str('redis_host'),
        port=configuration.get_int('redis_port'),
        db=configuration.get_int('redis_db'),
        )
    return instance

REDIS = init()
