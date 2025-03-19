import os
import subprocess

from flask import current_app, make_response, url_for, wrappers

from . import template


class BaseView:
    def __init__(self) -> None:
        super().__init__()
        self.content: str = ''
        self.has_cards: bool = False

    def home_url(self) -> str:
        return url_for('home')

    def template(self) -> str:
        return self.__class__.__name__.lower()

    def render_content(self) -> str:
        return template.render(self)

    def page(self) -> str:
        # Force prepare to happen before header and footer are rendered.
        self.content = self.render_content()
        return template.render_name('page', self)

    def response(self) -> wrappers.Response:
        return make_response(self.page())

    def prepare(self) -> None:
        pass

    def commit_id(self, path: str | None = None) -> str:
        if not path:
            return current_app.config['commit-id']
        key = f'commit-id-{path}'
        commit = current_app.config.get(key, None)
        if commit is None:
            args = ['git', 'log', '--format="%H"', '-n', '1', path]
            commit = subprocess.check_output(args, text=True).strip('\n').strip('"')
            current_app.config[key] = commit
        return commit

    def git_branch(self) -> str:
        return current_app.config['branch']

    def font_url(self) -> str:
        try:
            mtime = int(os.path.getmtime('shared_web/static/fonts/symbols.woff2'))
        except OSError:
            mtime = 0
        return url_for('static', filename='fonts/symbols.woff2', v=mtime)

    def css_url(self) -> str:
        return current_app.config['css_url'] or url_for('static', filename='css/pd.css', v=self.commit_id('shared_web/static/css/pd.css'))

    def tooltips_url(self) -> str | None:
        if not self.has_cards and not hasattr(self, 'cards'):
            return None
        return url_for('static', filename='js/tooltips.js', v=self.commit_id())

    def js_url(self) -> str:
        return current_app.config['js_url'] or url_for('static', filename='js/pd.js', v=self.commit_id('shared_web/static/js/pd.js'))

    def bundle_url(self) -> str:
        return url_for('static', filename='dist/bundle.js', v=self.commit_id('shared_web/static/js/'))

    def language_icon(self) -> str:
        return url_for('static', filename='images/language_icon.svg')

    def menu(self) -> list[dict[str, str | dict[str, str]]]:
        return current_app.config['menu']()
