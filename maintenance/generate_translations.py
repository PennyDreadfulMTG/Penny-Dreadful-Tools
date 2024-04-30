import subprocess
from collections.abc import Generator
from distutils.dist import Distribution
from typing import Any

import pystache
from babel.messages import frontend
from poeditor.client import POEditorAPI

from shared import configuration
from shared_web import template


def ad_hoc() -> int:
    dist = Distribution(dict(
        name='Penny-Dreadful-Tools',
    ))
    dist.message_extractors = {  # type: ignore
        'decksite': [
            ('**.py', 'python', {}),
            ('**.mustache', extract_mustache, {}),
        ],
        'logsite': [
            ('**.py', 'python', {}),
            ('**.mustache', extract_mustache, {}),
        ],
    }
    compiler = frontend.extract_messages(dist)  # type: ignore
    compiler.initialize_options()  # type: ignore
    compiler.output_file = './shared_web/translations/messages.pot'
    compiler.input_paths = ['decksite', 'logsite']
    compiler.finalize_options()  # type: ignore
    compiler.run()  # type: ignore

    api_key = configuration.get('poeditor_api_key')
    if api_key is None:
        return exitcode()
    client = POEditorAPI(api_token=api_key)
    client.update_terms('162959', './shared_web/translations/messages.pot')
    return exitcode()

def exitcode() -> int:
    numstat = subprocess.check_output(['git', 'diff', '--numstat']).strip().decode().split('\n')
    for line in numstat:
        added, deleted, path = line.split('\t')
        if path.endswith('messages.pot'):
            if int(added) > 1:
                # POT-Creation-Date will always change, we need to check for an additional change.
                return max(int(added), int(deleted)) - 1
    return 0

def extract_mustache(fileobj: Any, keywords: list[str], comment_tags: list[str], options: dict[str, str]) -> Generator:
    """Extract messages from mustache files.

    :param fileobj: the file-like object the messages should be extracted
                    from
    :param keywords: a list of keywords (i.e. function names) that should
                     be recognized as translation functions
    :param comment_tags: a list of translator tags to search for and
                         include in the results
    :param options: a dictionary of additional options (optional)
    :return: an iterator over ``(lineno, funcname, message, comments)``
             tuples
    :rtype: ``iterator``
    """
    source = fileobj.read().decode(options.get('encoding', 'utf-8'))
    tree = template.insert_gettext_nodes(pystache.parse(source))
    for node in tree._parse_tree:
        if isinstance(node, template._GettextNode):
            yield 1, None, node.key, []
