import re
import subprocess

from shared import fetch_tools
from shared.pd_exception import DoesNotExistException

PATH = 'shared_web/templates/jsdependencies.mustache'


def ad_hoc() -> None:
    tags = [fetch_script_tag(library) + '\n' for library in get_dependencies() if len(library) > 0]
    output = ''.join(tags)
    write_dependencies(output)
    send_pr_if_updated()


def get_dependencies() -> list[str]:
    f = open('shared_web/jsdependencies.txt')
    return [line.strip() for line in f.readlines()]


def write_dependencies(s: str) -> None:
    f = open(PATH, 'w')
    f.write(s)


def send_pr_if_updated() -> None:
    subprocess.call(['git', 'add', PATH])
    if subprocess.call(['git', 'commit', '-m', 'Update client dependencies.']) == 0:
        subprocess.call(['git', 'push'])
        subprocess.call(['hub', 'pull-request', '-b', 'master', '-m', 'Update client dependencies.', '-f'])


def fetch_script_tag(entry: str) -> str:
    parts = entry.split(':')
    library = parts[0]
    file = parts[0] if len(parts) == 1 else parts[1]
    info = fetch_tools.fetch_json(f'https://api.cdnjs.com/libraries/{library}')
    version = info.get('version')
    if not version and library.lower() != library:
        library = library.lower()
        info = fetch_tools.fetch_json(f'https://api.cdnjs.com/libraries/{library}')
        version = info.get('version')
    if not version:
        raise DoesNotExistException(f'Could not get version for {library}')
    path = None
    for a in info['assets']:
        if a.get('version') == version:
            for f in a['files']:
                if minified_path(f, file):
                    path = f
                    break
                if unminified_path(f, file):
                    path = f
    if not path:
        raise DoesNotExistException(f'Could not find file for {library}')
    return f'<script defer src="//cdnjs.cloudflare.com/ajax/libs/{library}/{version}/{path}"></script>'


def minified_path(path: str, library: str) -> bool:
    return test_path(path, library, '.min')


def unminified_path(path: str, library: str) -> bool:
    return test_path(path, library)


def test_path(path: str, library: str, required: str = '') -> bool:
    # CommonJS libs get us the error 'require is not defined' in the browser. See #6731.
    if 'cjs/' in path:
        return False
    name_without_js = library.replace('.js', '')
    regex = rf'{name_without_js}(.js)?(.production)?{required}.js$'
    return bool(re.search(regex, path, re.IGNORECASE))
