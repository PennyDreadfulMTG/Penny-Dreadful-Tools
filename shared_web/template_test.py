import glob
import os.path

import pytest

from shared_web import template


@pytest.mark.parametrize('module', ['decksite', 'logsite'])
def test_render_name(module: str) -> None:
    template.__SEARCHPATH.clear()
    template.__SEARCHPATH.append('{0}/templates'.format(module))
    templates = glob.glob('{0}/*.mustache'.format(module), recursive=True)
    for t in templates:
        template.render_name(os.path.basename(t).replace('.mustache', ''), {})
