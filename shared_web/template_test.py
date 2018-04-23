import glob
import os.path

from shared_web import template


def test_render_name():
    template.__SEARCHPATH.extend(['decksite/templates', 'logsite/templates']) # pylint: disable=protected-access
    templates = glob.glob('**/*.mustache', recursive=True)
    print(templates)
    for t in templates:
        template.render_name(os.path.basename(t).replace('.mustache', ''), {})
