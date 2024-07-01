import json
from typing import Any, AnyStr, TypeVar

import redis as redislib

from . import configuration
from .container import Container
from .serialization import extra_serializer


def init() -> redislib.Redis | None:
    if not configuration.redis_enabled.value:
        return None
    instance = redislib.Redis(
        host=configuration.get_str('redis_host'),
        port=configuration.get_int('redis_port'),
        db=configuration.get_int('redis_db'),
    )
    try:
        instance.ping()
    except redislib.exceptions.ConnectionError:
        return None
    return instance


REDIS = init()


def enabled() -> bool:
    return REDIS is not None


def _get(key: str, ex: int | None = None) -> bytes | None:
    try:
        if REDIS is not None:
            blob = REDIS.get(key)
            if blob is not None:
                if ex is not None:
                    REDIS.set(key, blob, ex=ex)
                return blob
    except redislib.exceptions.BusyLoadingError:
        pass
    except redislib.exceptions.ConnectionError:
        pass
    return None


def get_str(key: str, ex: int | None = None) -> str | None:
    if REDIS is not None:
        blob = _get(key, ex)
        if blob is not None:
            val = json.loads(blob)
            if val is not None:
                return val
    return None


def get_bool(key: str, ex: int | None = None) -> bool:
    if REDIS is not None:
        blob = _get(key, ex)
        if blob is None:
            return False
        return bool(json.loads(blob))
    return False


def get_container(key: str, ex: int | None = None) -> Container | None:
    if REDIS is not None:
        blob = _get(key, ex)
        if blob is not None:
            val = json.loads(blob)
            if val is not None:
                return Container(val)
    return None


def get_int(key: str, ex: int | None = None) -> int | None:
    if REDIS is not None:
        blob = _get(key, ex)
        if blob is not None:
            val = json.loads(blob)
            if val is not None:
                return val
    return None


def get_list(key: str) -> list[Any] | None:
    if REDIS is not None:
        blob = _get(key)
        if blob is not None:
            val = json.loads(blob)
            return val
    return None


def get_dict(key: str) -> dict | None:
    if REDIS is not None:
        blob = _get(key)
        if blob is not None:
            return json.loads(blob)
    return None


def get_container_list(key: str) -> list[Container] | None:
    if REDIS is not None:
        blob = _get(key)
        if blob is not None:
            val = json.loads(blob)
            return [Container(d) for d in val]
    return None


T = TypeVar('T', dict, list, str, bool, int, covariant=True)


def store(key: str, val: T, **kwargs: Any) -> T:
    if REDIS is not None:
        try:
            REDIS.set(key, json.dumps(val, default=extra_serializer), **kwargs)
        except redislib.exceptions.BusyLoadingError:
            pass
        except redislib.exceptions.ConnectionError:
            pass
    return val


def increment(key: str, **kwargs: Any) -> int | None:
    if REDIS is not None:
        try:
            return REDIS.incr(key, **kwargs)
        except redislib.exceptions.BusyLoadingError:
            pass
        except redislib.exceptions.ConnectionError:
            pass
    return None


def clear(*keys_list: AnyStr) -> None:
    if REDIS is not None:
        if len(keys_list) == 0:
            # redis errors on a delete with no arguments, but we don't have to
            return
        REDIS.delete(*keys_list)


def expire(key: str, time: int) -> None:
    if REDIS is not None:
        try:
            REDIS.expire(key, time)
        except redislib.exceptions.BusyLoadingError:
            pass
        except redislib.exceptions.ConnectionError:
            pass


def keys(pattern: str) -> list[bytes]:
    if REDIS is not None:
        return REDIS.keys(pattern)
    return []


def sadd(key: str, *values: Any, ex: int | None = None) -> None:
    if REDIS is not None:
        REDIS.sadd(key, *values)
        if ex is not None:
            REDIS.expire(key, ex)


def sismember(key: str, value: str) -> bool:
    if REDIS is not None:
        return REDIS.sismember(key, value)
    return False
