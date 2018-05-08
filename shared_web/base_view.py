from typing import Dict, List, Optional, Union

from flask import current_app, url_for

from . import template


# pylint: disable=no-self-use, too-many-public-methods
class BaseView:
    def template(self) -> str:
        return self.__class__.__name__.lower()

    def content(self) -> str:
        return template.render(self)

    def page(self) -> str:
        return template.render_name('page', self)

    def prepare(self) -> None:
        return

    def commit_id(self) -> str:
        return current_app.config['commit-id']

    def git_branch(self) -> str:
        return current_app.config['branch']

    def css_url(self) -> str:
        return current_app.config['css_url'] or url_for('static', filename='css/pd.css', v=self.commit_id())

    def tooltips_url(self) -> Optional[str]:
        # Don't preload 10,000 images.
        # pylint: disable=no-member
        if not hasattr(self, 'cards') or len(getattr(self, 'cards')) > 500:
            return None
        return url_for('static', filename='js/tooltips.js', v=self.commit_id())

    def js_url(self) -> str:
        return current_app.config['js_url'] or url_for('static', filename='js/pd.js', v=self.commit_id())

    def language_icon(self):
        return url_for('static', filename='images/language_icon.svg')

    def menu(self) -> List[Dict[str, Union[str, Dict[str, str]]]]:
        return current_app.config['menu']()
