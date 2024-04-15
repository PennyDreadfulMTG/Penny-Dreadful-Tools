import json

import requests
from lxml import etree

from . import repo


def main() -> None:
    manifest = requests.get('http://mtgo.patch.daybreakgames.com/patch/mtg/live/client/MTGO.application')
    tree = etree.fromstring(manifest.content)
    identity = tree.find('{urn:schemas-microsoft-com:asm.v1}assemblyIdentity')
    version = identity.attrib['version']

    print(f'Current MTGO Version is {version}')

    data = {'version': version}
    with open('mtgo_version.json', mode='w') as f:
        json.dump(data, f)

    project = repo.get_verification_project()
    current = [c for c in project.get_columns() if c.name == version]
    if not current:
        print(f'Creating column for {version}')
        project.create_column(version)
    for col in project.get_columns():
        print('Updating Verification Model')
        if col.name in ['Needs Testing', version]:
            continue
        print(f'... {col.name}')
        keep = False
        for card in col.get_cards():
            content = card.get_content()
            if content is None:
                continue
            # print(f'... ... {content.title} = {content.state}')
            if content.state == 'open':
                keep = True
            elif not card.archived:
                card.edit(archived=True)
        if not keep:
            print(f'Deleting empty column {col.name}')
            col.delete()
    print('... Done')
