import re
import xml.etree.ElementTree as etree
from collections.abc import Callable
from re import Match
from typing import TYPE_CHECKING, Optional

import flask
import pystache
import pystache.parsed
from flask_babel import gettext
from markdown import Markdown, markdown
from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor
from pystache.common import TemplateNotFoundError
from pystache.context import ContextStack

if TYPE_CHECKING:
    from shared_web.base_view import BaseView

__SEARCHPATH: list[str] = []

StringConverterFunction = Optional[Callable[[str], str]]


def render_name(template: str, *context: ContextStack) -> str:
    try:
        renderer = CachedRenderer(search_dirs=[f'{flask.current_app.name}/templates', 'shared_web/templates'])
    except TemplateNotFoundError:
        renderer = CachedRenderer(search_dirs=__SEARCHPATH)
    return renderer.render_name(template, *context)


def render(view: 'BaseView') -> str:
    view.prepare()
    return render_name(view.template(), view)


# Subclass pystache.Renderer to provide our custom caching versions of pystache classes for performance reasons.
class CachedRenderer(pystache.Renderer):
    def _make_loader(self) -> pystache.loader.Loader:
        return CachedLoader(file_encoding=self.file_encoding, extension=self.file_extension, to_unicode=self.str, search_dirs=self.search_dirs)

    def _make_render_engine(self) -> pystache.renderengine.RenderEngine:
        resolve_context = self._make_resolve_context()
        resolve_partial = self._make_resolve_partial()
        engine = CachedRenderEngine(literal=self._to_unicode_hard, escape=self._escape_to_unicode, resolve_context=resolve_context, resolve_partial=resolve_partial, to_str=self.str_coerce)
        return engine


# A custom loader that acts exactly as the default loader but only loads a given file once to speed up repeated use of partials.
# This will stop us loading record.mustache from disk 16,000 times on /cards/ for example.
class CachedLoader(pystache.loader.Loader):
    def __init__(self, file_encoding: str | None = None, extension: str | bool | None = None, to_unicode: StringConverterFunction | None = None, search_dirs: list[str] | None = None) -> None:
        super().__init__(file_encoding, extension, to_unicode, search_dirs)
        self.templates: dict[str, str] = {}

    def read(self, path: str, encoding: str | None = None) -> str:
        if self.templates.get(path) is None:
            self.templates[path] = super().read(path, encoding)
        return self.templates[path]


# If you have already parsed a template, don't parse it again.
class CachedRenderEngine(pystache.renderengine.RenderEngine):
    def __init__(self, literal: StringConverterFunction | None = None, escape: StringConverterFunction | None = None, resolve_context: Callable[[ContextStack, str], str] | None = None, resolve_partial: StringConverterFunction | None = None, to_str: Callable[[object], str] | None = None) -> None:
        super().__init__(literal, escape, resolve_context, resolve_partial, to_str)
        self.parsed_templates: dict[str, pystache.parsed.ParsedTemplate] = {}

    def render(self, template: str, context_stack: ContextStack, delimiters: tuple[str, str] | None = None) -> str:
        if self.parsed_templates.get(template) is None:
            self.parsed_templates[template] = insert_gettext_nodes(pystache.parser.parse(template, delimiters))
        return self.parsed_templates[template].render(self, context_stack)


# Localization Shim
def insert_gettext_nodes(parsed_template: pystache.parsed.ParsedTemplate) -> pystache.parsed.ParsedTemplate:
    new_template = pystache.parsed.ParsedTemplate()
    for node in parsed_template._parse_tree:
        if isinstance(node, pystache.parser._EscapeNode):
            if node.key[0:2] == '_ ':
                key = node.key[2:].strip()
                new_template.add(_GettextNode(key))
            else:
                new_template.add(node)
        elif isinstance(node, pystache.parser._InvertedNode):
            new_template.add(pystache.parser._InvertedNode(node.key, insert_gettext_nodes(node.parsed_section)))
        elif isinstance(node, pystache.parser._SectionNode):
            new_template.add(pystache.parser._SectionNode(node.key, insert_gettext_nodes(node.parsed), node.delimiters, node.template, node.index_begin, node.index_end))
        else:
            new_template.add(node)
        # We may need to iterate into Sections and Inverted nodes
    return new_template


class _GettextNode:
    def __init__(self, key: str) -> None:
        self.key = key

    def __repr__(self) -> str:
        return pystache.parser._format(self)

    def render(self, engine: pystache.renderengine.RenderEngine, context: ContextStack) -> str:
        s = gettext(self.key)  # The key is populated in messages.pot via generate_translations.py

        def lookup(match: Match) -> str:
            return engine.fetch_string(context, match.group(1))

        s = re.sub(r'\{([a-z_]+)\}', lookup, s)
        return markdown(engine.escape(s), extensions=[NoParaTagsExtension()])


class NoParaTagProcessor(Treeprocessor):
    def run(self, root: etree.Element) -> None:
        root[0].tag = 'span'


class NoParaTagsExtension(Extension):
    def extendMarkdown(self, md: Markdown) -> None:
        md.treeprocessors.register(NoParaTagProcessor(), 'noparatag', -50)
