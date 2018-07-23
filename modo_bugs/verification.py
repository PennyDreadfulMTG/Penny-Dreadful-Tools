import requests
from lxml import etree

def main() -> None:
    manifest = requests.get('http://mtgoclientdepot.onlinegaming.wizards.com/MTGO.application')
    tree = etree.fromstring(manifest.content)
    identity = tree.find('{urn:schemas-microsoft-com:asm.v1}assemblyIdentity')
    version = identity.attrib['version']

    print('Current MTGO Version is {0}'.format(version))
