import collections.abc
import warnings
from collections.abc import Mapping, MutableMapping
from typing import Any


def rupdate[K](base: MutableMapping[K, Any], new_data: Mapping[K, Any]) -> MutableMapping[K, Any]:
    for k, v in new_data.items():
        if isinstance(v, collections.abc.Mapping):
            base[k] = rupdate(base.get(k, {}), v)
        elif base.get(k) == v:
            warnings.warn(UserWarning(f'Overriding identical value {k}={v}'), stacklevel=2)
        else:
            base[k] = v
    return base
