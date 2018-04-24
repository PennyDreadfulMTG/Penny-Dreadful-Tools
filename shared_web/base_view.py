from . import template


# pylint: disable=no-self-use, too-many-public-methods
class BaseView:
    def template(self):
        return self.__class__.__name__.lower()

    def content(self):
        return template.render(self)

    def page(self):
        return template.render_name('page', self)
