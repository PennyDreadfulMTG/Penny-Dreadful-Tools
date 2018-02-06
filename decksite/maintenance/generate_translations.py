import subprocess

from poeditor.client import POEditorAPI

from shared import configuration

def ad_hoc():
    subprocess.run(['pybabel', 'extract', '-F', 'babel.cfg', '-o', './decksite/translations/messages.pot', 'decksite'])
    api_key = configuration.get("poeditor_api_key")
    if api_key is None:
        return
    client = POEditorAPI(api_token=api_key)
    client.update_terms("162959", './decksite/translations/messages.pot')
