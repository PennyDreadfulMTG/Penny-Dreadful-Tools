import glob
import os.path

from decksite import template


def test_render_name():
    templates = glob.glob('**/*.mustache', recursive=True)
    print(templates)
    for t in templates:
        template.render_name(os.path.basename(t).replace('.mustache', ''), {})
