import re
import subprocess
from typing import List

from shared import fetch_tools

PATH = 'shared_web/templates/jsdependencies.mustache'

def ad_hoc() -> None:
    tags = [fetch_script_tag(library) + '\n' for library in get_dependencies()]
    output = ''.join(tags)
    write_dependencies(output)
    subprocess.call(['git', 'add', PATH])
    if subprocess.call(['git', 'commit', '-m', '"Update client dependencies."']) == 0:
        subprocess.call(['git', 'push'])
        subprocess.call(['hub', 'pull-request', '-b', 'master', '-m', 'Update client dependencies.', '-f'])

def get_dependencies() -> List[str]:
    f = open('shared_web/jsrequirements.txt', 'r')
    return [line.strip() for line in f.readlines()]

def write_dependencies(s: str) -> None:
    f = open(PATH, 'w')
    f.write(s)

def fetch_script_tag(library: str) -> str:
    info = fetch_tools.fetch_json(f'https://api.cdnjs.com/libraries/{library}')
    version = info.get('version')
    if not version and library.lower() != library:
        library = library.lower()
        info = fetch_tools.fetch_json(f'https://api.cdnjs.com/libraries/{library}')
        version = info.get('version')
    if not version:
        raise Exception(f'Could not get version for {library}') # BAKER exception type
    path = None
    for a in info['assets']:
        if a.get('version') == version:
            for f in a['files']:
                if minified_path(f, library):
                    path = f
                    break
                if unminified_path(f, library):
                    path = f
    if not path:
        raise Exception(f'Could not find file for {library}') # BAKERT exception type
    return f'<script defer src="//cdnjs.cloudflare.com/ajax/libs/{library}/{version}/{path}"></script>'

def minified_path(path: str, library: str) -> bool:
    return test_path(path, library, '.min')

def unminified_path(path: str, library: str) -> bool:
    return test_path(path, library)

def test_path(path: str, library: str, required: str = '') -> bool:
    name_without_js = library.replace('.js', '')
    regex = fr'{name_without_js}(.js)?(.production)?{required}.js$'
    return bool(re.search(regex, path, re.IGNORECASE))
