from typing import Optional

from flask import url_for

from shared_web.base_view import BaseView


# pylint: disable=no-self-use, too-many-public-methods
class View(BaseView):
    def js_extra_url(self) -> Optional[str]:
        pass

    def favicon_url(self) -> str:
        return url_for('favicon', rest='.ico')

    def favicon_152_url(self) -> str:
        return url_for('favicon', rest='-152.png')

    def title(self) -> str:
        if not self.subtitle():
            return 'PDBot Logs'
        return '{subtitle} – PDBot Logs'.format(subtitle=self.subtitle())

    def subtitle(self) -> Optional[str]:
        pass
