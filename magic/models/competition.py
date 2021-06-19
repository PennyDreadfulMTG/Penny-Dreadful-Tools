from typing import Any, Dict

from shared.container import Container


class Competition(Container):
    def __init__(self, params: Dict[str, Any]) -> None:
        super().__init__(params)
        self.base_archetype_data: Dict[str, int] = {}
