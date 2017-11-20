import pystache

def render_name(template, *context):
    return CachedRenderer(search_dirs=['decksite/templates']).render_name(template, *context)

def render(view):
    view.prepare()
    return render_name(view.template(), view)

# Subclass pystache.Renderer to provide our custom caching versions of pystache classes for performance reasons.
class CachedRenderer(pystache.Renderer):
    def _make_loader(self):
        return CachedLoader(file_encoding=self.file_encoding, extension=self.file_extension, to_unicode=self.str, search_dirs=self.search_dirs)

    def _make_render_engine(self):
        resolve_context = self._make_resolve_context()
        resolve_partial = self._make_resolve_partial()
        engine = CachedRenderEngine(literal=self._to_unicode_hard, escape=self._escape_to_unicode, resolve_context=resolve_context, resolve_partial=resolve_partial, to_str=self.str_coerce)
        return engine

# A custom loader that acts exactly as the default loader but only loads a given file once to speed up repeated use of partials.
# This will stop us loading record.mustache from disk 16,000 times on /cards/ for example.
class CachedLoader(pystache.loader.Loader):
    def __init__(self, file_encoding=None, extension=None, to_unicode=None, search_dirs=None):
        super().__init__(file_encoding, extension, to_unicode, search_dirs)
        self.templates = {}

    def read(self, path, encoding=None):
        if self.templates.get(path) is None:
            self.templates[path] = super().read(path, encoding)
        return self.templates[path]

# If you have already parsed a template, don't parse it again.
class CachedRenderEngine(pystache.renderengine.RenderEngine):
    def __init__(self, literal=None, escape=None, resolve_context=None, resolve_partial=None, to_str=None):
        super().__init__(literal, escape, resolve_context, resolve_partial, to_str)
        self.parsed_templates = {}

    def render(self, template, context_stack, delimiters=None):
        if self.parsed_templates.get(template) is None:
            self.parsed_templates[template] = pystache.parser.parse(template, delimiters)
        return self.parsed_templates[template].render(self, context_stack)
