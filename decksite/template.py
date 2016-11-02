import pystache

def render_name(template, *context):
    renderer = pystache.Renderer(search_dirs=['decksite/templates'])
    return renderer.render_name(template, *context)

def render(view):
    view.prepare()
    return render_name(view.template(), view)
