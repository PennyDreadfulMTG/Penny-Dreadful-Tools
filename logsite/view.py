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
        if not self.page_title():
            return 'PDBot Logs'
        return f'{self.page_title()} – PDBot Logs'

    def page_title(self) -> str:
        return ''
