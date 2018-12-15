from typing import Optional

from .error import ErrorView


# pylint: disable=no-self-use
class Unauthorized(ErrorView):
    def __init__(self, error: Optional[str]) -> None:
        super().__init__()
        if error:
            self.error = error

    def page_title(self) -> str:
        return 'Unauthorized'
