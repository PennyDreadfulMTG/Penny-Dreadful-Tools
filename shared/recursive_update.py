import collections.abc
import warnings
from typing import Any, TypeVar
from collections.abc import Mapping, MutableMapping

K = TypeVar('K')
V = Any


def rupdate(base: MutableMapping[K, V], new_data: Mapping[K, V]) -> MutableMapping[K, V]:
    for k, v in new_data.items():
        if isinstance(v, collections.abc.Mapping):
            base[k] = rupdate(base.get(k, {}), v)
        elif base.get(k) == v:
            warnings.warn(UserWarning(f'Overriding identical value {k}={v}'), stacklevel=2)
        else:
            base[k] = v
    return base
