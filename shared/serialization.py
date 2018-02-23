import datetime
import decimal


def extra_serializer(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    elif isinstance(obj, bytes):
        return obj.decode('utf-8')
    elif isinstance(obj, decimal.Decimal):
        return obj.to_eng_string()
    elif isinstance(obj, set) or type(obj) == 'dict_keys': # pylint: disable=unidiomatic-typecheck
        return list(obj)

    raise TypeError("Type {t} not serializable - {obj}".format(t=type(obj), obj=obj))
