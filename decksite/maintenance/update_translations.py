import os

from babel.messages.frontend import compile_catalog
from poeditor.client import POEditorAPI

from shared import configuration


def run():
    api_key = configuration.get("poeditor_api_key")
    if api_key is None:
        print("Missing poeditor.com API key")
        return
    client = POEditorAPI(api_token=api_key)
    languages = client.list_project_languages("162959")
    # pull down translations
    for locale in languages:
        print("Found translation for {code}: {percent}%".format(code=locale['code'], percent=locale['percentage']))
        if locale['percentage'] > 0:
            path = os.path.join('decksite', 'translations', locale['code'].replace('-', '_'), 'LC_MESSAGES')
            if not os.path.exists(path):
                os.makedirs(path)
            pofile = os.path.join(path, 'messages.po')
            print('Saving to {0}'.format(pofile))
            if os.path.exists(pofile):
                os.remove(pofile)
            client.export("162959", locale['code'], local_file=pofile)
    # Compile .po files into .mo files
    compiler = compile_catalog()
    compiler.directory = os.path.join('decksite', 'translations')
    compiler.domain = ['messages']
    compiler.run()
    # hack for English - We need an empty folder so that Enlish shows up in the 'Known Languages' list.
    path = os.path.join('decksite', 'translations', 'en', 'LC_MESSAGES')
    if not os.path.exists(path):
        os.makedirs(path)
