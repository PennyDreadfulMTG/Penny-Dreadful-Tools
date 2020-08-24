from typing import Any

from munch import Munch


# pylint: disable=too-many-instance-attributes
class Container(Munch):
    # Reverse the order of operations from Munch because it gives us a speedup when we access hundreds of thousands of properties in a request.
    def __getattr__(self, k: str) -> Any:
        try:
            return self[k]
        except KeyError:
            try:
                return object.__getattribute__(self, k)
            except AttributeError as e:
                raise AttributeError(k) from e
