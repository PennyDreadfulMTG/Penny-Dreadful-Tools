from . import template


class BaseView:
    def template(self) -> str:
        return self.__class__.__name__.lower()

    def content(self) -> str:
        return template.render(self)

    def page(self) -> str:
        return template.render_name('page', self)

    def prepare(self) -> None:
        raise NotImplementedError
