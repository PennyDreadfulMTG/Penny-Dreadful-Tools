from typing import Any

from shared.container import Container


class Competition(Container):
    def __init__(self, params: dict[str, Any]) -> None:
        super().__init__(params)
        self.base_archetype_data: dict[str, int] = {}
