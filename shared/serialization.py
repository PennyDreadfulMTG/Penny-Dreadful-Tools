import datetime
import decimal
import traceback
from collections.abc import KeysView
from typing import Any

from shared import dtutil


def extra_serializer(obj: Any) -> int | str | list[Any] | dict[str, Any]:
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, datetime.datetime):
        return dtutil.dt2ts(obj)
    if isinstance(obj, bytes):
        return obj.decode('utf-8')
    if isinstance(obj, decimal.Decimal):
        return obj.to_eng_string()
    if isinstance(obj, (set, KeysView)):
        return list(obj)
    if isinstance(obj, Exception):
        stack = traceback.extract_tb(obj.__traceback__)
        return traceback.format_list(stack)
    if hasattr(obj, 'to_dict'):
        return obj.to_dict()
    if hasattr(obj, '__attrs_attrs__'):
        val: dict[str, Any] = {}
        for a in obj.__attrs_attrs__:
            val[a.name] = getattr(obj, a.name)
        return val
    raise TypeError(f'Type {type(obj)} not serializable - {obj}')
