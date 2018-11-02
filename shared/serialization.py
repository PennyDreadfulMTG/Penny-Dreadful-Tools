import datetime
import decimal
import traceback
from typing import Any, List, Union

from shared import dtutil


def extra_serializer(obj: Any) -> Union[int, str, List[Any]]:
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, datetime.datetime):
        return dtutil.dt2ts(obj)
    if isinstance(obj, bytes):
        return obj.decode('utf-8')
    if isinstance(obj, decimal.Decimal):
        return obj.to_eng_string()
    if isinstance(obj, set) or type(obj) == 'dict_keys': # pylint: disable=unidiomatic-typecheck
        return list(obj)
    if isinstance(obj, Exception):
        stack = traceback.extract_tb(obj.__traceback__)
        return traceback.format_list(stack)
    raise TypeError('Type {t} not serializable - {obj}'.format(t=type(obj), obj=obj))
