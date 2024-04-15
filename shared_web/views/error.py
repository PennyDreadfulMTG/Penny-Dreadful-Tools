import urllib.parse

from flask import url_for

from shared.container import Container

from ..base_view import BaseView


class ErrorView(BaseView):
    def __init__(self) -> None:
        super().__init__()
        self.is_error_page = True

    def make_card(self, c: str | Container) -> Container:
        # If the server is throwing errors, we don't want to rely on oracle.
        # Make a minimal viable Card-alike object
        if not isinstance(c, str):
            return c
        container = Container({
            'name': c,
            'url': url_for('.card', name=c),
            'img_url': f'https://pennydreadfulmagic.com/image/{urllib.parse.quote(c)}/',
        })
        return container
