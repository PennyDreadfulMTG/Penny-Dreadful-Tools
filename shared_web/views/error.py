import urllib
from typing import Union

from flask import url_for

from shared.container import Container

from ..base_view import BaseView


# pylint: disable=no-self-use
class ErrorView(BaseView):
    def make_card(self, c: Union[str, Container]) -> Container:
        # If the server is throwing errors, we don't want to rely on oracle.
        # Make a minimal viable Card-alike object
        if isinstance(c, str):
            return Container({
                'name': c,
                'url': url_for('card', name=c),
                'img_url': 'http://magic.bluebones.net/proxies/index2.php?c={name}'.format(name=urllib.parse.quote(c)), # type: ignore
            })
        return c
