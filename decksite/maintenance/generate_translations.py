from distutils.dist import Distribution

import pystache
from babel.messages import frontend
from poeditor.client import POEditorAPI

from shared import configuration

from .. import template


def ad_hoc():
    dist = Distribution(dict(
        name='Penny-Dreadful-Tools'
    ))
    dist.message_extractors = {
        'decksite': [
            ('**.py', 'python', {}),
            ('**.mustache', extract_mustache, {})
        ]
    }
    compiler = frontend.extract_messages(dist)
    compiler.initialize_options()
    compiler.output_file = './decksite/translations/messages.pot'
    compiler.input_paths = 'decksite'
    compiler.finalize_options()
    compiler.run()

    api_key = configuration.get("poeditor_api_key")
    if api_key is None:
        return
    client = POEditorAPI(api_token=api_key)
    client.update_terms("162959", './decksite/translations/messages.pot')

# pylint: disable=protected-access, unused-argument
def extract_mustache(fileobj, keywords, comment_tags, options):
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
