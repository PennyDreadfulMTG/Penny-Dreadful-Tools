import os

from babel.messages.frontend import compile_catalog
from poeditor.client import POEditorAPI

from shared import configuration
from shared import logger

from . import validate_translations


def run() -> None:
    api_key = configuration.get('poeditor_api_key')
    if api_key is None:
        logger.warning('Missing poeditor.com API key')
        return
    client = POEditorAPI(api_token=api_key)
    languages = client.list_project_languages('162959')
    # pull down translations
    for locale in languages:
        logger.warning('Found translation for {code}: {percent}%'.format(code=locale['code'], percent=locale['percentage']))
        if locale['percentage'] > 0:
            path = os.path.join('shared_web', 'translations', locale['code'].replace('-', '_'), 'LC_MESSAGES')
            if not os.path.exists(path):
                os.makedirs(path)
            pofile = os.path.join(path, 'messages.po')
            logger.warning('Saving to {0}'.format(pofile))
            if os.path.exists(pofile):
                os.remove(pofile)
            client.export(project_id='162959', language_code=locale['code'],
                          local_file=pofile, filters=['translated', 'not_fuzzy'])

    # Compile .po files into .mo files
    validate_translations.ad_hoc()
    compiler = compile_catalog()
    compiler.directory = os.path.join('shared_web', 'translations')
    compiler.domain = ['messages']
    compiler.run()
    # hack for English - We need an empty folder so that Enlish shows up in the 'Known Languages' list.
    path = os.path.join('shared_web', 'translations', 'en', 'LC_MESSAGES')
    if not os.path.exists(path):
        os.makedirs(path)
