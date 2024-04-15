#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time
from typing import Iterable, List, Optional, Union

import build as builddotpy
from run import wait_for_db
from shared import configuration

try:
    import click
    from plumbum import FG, local
    from plumbum.commands.processes import ProcessExecutionError
except ImportError:
    sys.stderr.write('Please run ./build.py first\n')
    sys.exit(-1)


ON_PROD = configuration.production.value
if ON_PROD:
    sys.stderr.write('DO NOT RUN dev.py ON PROD\n')
    sys.exit(1)

ON_WINDOWS = sys.platform == 'win32'


@click.group()
@click.option('--wait-for-db', is_flag=True, callback=wait_for_db, expose_value=False, help='Idle until the mySQL server starts accepting connections')
def cli() -> None:
    pass

@cli.command()
def build() -> None:
    builddotpy.build()

@cli.command()
def buildpy() -> None:
    builddotpy.buildpy()

@cli.command()
def buildjs() -> None:
    builddotpy.buildjs()

def do_lint() -> None:
    """
    Invoke linter with our preferred options
    """
    print('>>>> Running flake8')
    pipenv = local['pipenv']
    try:
        pipenv['run', 'python', '-m', 'flake8', '--exclude=node_modules'] & FG
    except ProcessExecutionError as e:
        sys.exit(e.retcode)

@cli.command()
def lint() -> None:
    do_lint()


@cli.command()
def stylefix() -> None:
    autopep = local['autopep8']
    autopep['--select', 'E123,E124,E261,E265,E303,E305,E306', '--in-place', '-r', '.'] & FG

def do_mypy(argv: List[str], strict: bool = False, typeshedding: bool = False) -> None:
    """
    Invoke mypy with our preferred options.
    Strict Mode enables additional checks that are currently failing (that we plan on integrating once they pass)
    """
    print('>>>> Typechecking')
    args = []
    if strict:
        args.extend([
            '--disallow-any-generics',  # Generic types like List or Dict need [T]
            # '--warn-return-any',        # Functions shouldn't return Any if we're expecting something better
            # '--disallow-any-unimported', # Catch import errors
        ])
    if typeshedding:
        args.extend([
            '--warn-return-any',
            '--custom-typeshed', '../typeshed',
        ])
    if os.environ.get('GITHUB_ACTOR') != 'dependabot[bot]':
        args.extend(['--warn-unused-ignores'])
    args.extend(argv or ['.'])  # Invoke on the entire project.

    print('mypy ' + ' '.join(args))
    from mypy import api
    result = api.run(args)
    if result[0]:
        print(result[0])  # stdout
    if result[1]:
        sys.stderr.write(result[1])  # stderr
    print('Exit status: {code} ({english})'.format(code=result[2], english='Failure' if result[2] else 'Success'))
    if result[2]:
        sys.exit(result[2])

@cli.command()
@click.argument('argv', nargs=-1)
def mypy(argv: List[str], strict: bool = False, typeshedding: bool = False) -> None:
    do_mypy(argv, strict, typeshedding)

@cli.command()
def upload_coverage() -> None:
    try:
        print('>>>> Upload coverage')
        from shared import fetch_tools
        fetch_tools.store('https://codecov.io/bash', 'codecov.sh')
        python3 = local['python3']
        python3['-m', 'coverage', 'xml', '-i']
        bash = local['bash']
        bash['codecov.sh'] & FG
        # Sometimes the coverage uploader has issues.  Just fail silently, it's not that important
    except ProcessExecutionError as e:
        print(e)
    except fetch_tools.FetchException as e:
        print(e)

def find_files(needle: str = '', file_extension: str = '', exclude: Optional[List[str]] = None) -> List[str]:
    paths = subprocess.check_output(['git', 'ls-files']).strip().decode().split('\n')
    paths = [p for p in paths if 'logsite_migrations' not in p]
    if file_extension:
        paths = [p for p in paths if p.endswith(file_extension)]
    if needle:
        paths = [p for p in paths if needle in os.path.basename(p)]
    if exclude:
        paths = [p for p in paths if p not in exclude]
    return paths

def runtests(argv: Iterable[str], m: str) -> None:
    args = []
    for arg in list(argv):
        args.extend(find_files(arg, 'py'))
    args.extend(['-x'])
    if m:
        args.extend(['-m', m])

    argstr = ' '.join(args)
    print(f'>>>> Running tests with "{argstr}"')
    import pytest

    code = pytest.main(args)
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        upload_coverage()
    if code:
        sys.exit(code)

def do_unit(argv: List[str]) -> None:
    runtests(argv, 'not functional and not perf')

@cli.command()
@click.argument('argv', nargs=-1)
def unit(argv: List[str]) -> None:
    do_unit(argv)

@cli.command()
@click.argument('argv', nargs=-1)
def test(argv: List[str]) -> None:
    runtests(argv, '')

def do_sort(fix: bool) -> None:
    print('>>>> Checking imports')
    pipenv = local['pipenv']
    if fix:
        pipenv['run', 'isort', '.', '--skip=node_modules'] & FG
    else:
        pipenv['run', 'isort', '.', '--check', '--skip=node_modules'] & FG

@cli.command()
@click.option('--fix', is_flag=True, default=False)
def sort(fix: bool = False) -> None:
    do_sort(fix)

@cli.command()
def reset_db() -> None:
    """
    Handle with care.
    """
    print('>>>> Reset db')
    import decksite.database
    decksite.database.db().nuke_database()
    import magic.database
    magic.database.db().nuke_database()

@cli.command()
def dev_db() -> None:
    # reset_db()
    print('>>>> Downloading dev db')
    import gzip

    import requests

    import decksite.database
    r = requests.get('https://pennydreadfulmagic.com/static/dev-db.sql.gz')
    r.raise_for_status()
    with open('dev-db.sql.gz', 'wb') as f:
        f.write(r.content)
    with gzip.open('dev-db.sql.gz', 'rb') as f:
        c = f.read()
        sql = c.decode()
        for stmt in sql.split(';'):
            if stmt.strip() != '':
                decksite.database.db().execute(stmt)

def do_push() -> None:
    print('>>>> Pushing')
    branch_name = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).strip().decode()
    subprocess.check_call(['git', 'push', '--set-upstream', 'origin', branch_name])

def stash_if_any() -> str:
    print('>>>> Stashing local changes')
    label = 'dev-py-stash-at-' + str(time.time())
    subprocess.check_call(['git', 'stash', 'save', '--include-untracked', label])
    return label

def pop_if_any(label: str) -> None:
    print('>>>> Checking for stashed changes')
    output = subprocess.check_output(['git', 'stash', 'list'], stderr=subprocess.STDOUT)
    if label in str(output):
        print('>>>> Popping stashed changes')
        subprocess.call(['git', 'stash', 'pop'])

def do_safe_push(argv: List[str]) -> None:
    label = stash_if_any()
    print('>>>> Rebasing branch on master')
    subprocess.check_call(['git', 'pull', 'origin', 'master', '--rebase'])
    do_unit(argv)
    do_push()
    pop_if_any(label)

@cli.command()
@click.argument('argv', nargs=-1)
def safe_push(argv: List[str]) -> None:
    do_safe_push(argv)

@cli.command()
def push() -> None:
    do_push()

def do_pull_request(argv: List[str]) -> None:
    print('>>>> Pull request')
    try:
        subprocess.check_call(['hub', 'pull-request', *argv])
    except (subprocess.CalledProcessError, FileNotFoundError):
        subprocess.check_call(['gh', 'pr', 'create'])

@cli.command()
@click.argument('argv', nargs=-1)
def pull_request(argv: List[str]) -> None:
    do_pull_request(argv)

def do_jslint(fix: bool) -> None:
    print('>>>> Linting javascript')
    files = find_files(file_extension='js', exclude=['.eslintrc.js', 'shared_web/static/js/tipped.min.js']) + find_files(file_extension='jsx')
    cmd = [os.path.join('.', 'node_modules', '.bin', 'eslint')]
    if fix:
        cmd.append('--fix')
    subprocess.check_call(cmd + files, shell=ON_WINDOWS)

@cli.command()
@click.option('--fix', is_flag=True, default=False)
def jslint(fix: bool = False) -> None:
    do_jslint(fix)

@cli.command()
def jsfix() -> None:
    print('>>>> Fixing js')
    do_jslint(fix=True)

@cli.command()
def coverage() -> None:
    print('>>>> Coverage')
    subprocess.check_call(['coverage', 'run', 'dev.py', 'tests'])
    subprocess.check_call(['coverage', 'xml'])
    subprocess.check_call(['coverage', 'report'])

@cli.command()
def watch() -> None:
    print('>>>> Watching')
    subprocess.check_call(['npm', 'run', 'watch'], shell=ON_WINDOWS)

@cli.command()
@click.argument('argv', nargs=-1)
def branch(args: List[str]) -> None:
    """Make a branch based off of current (remote) master with all your local changes preserved (but not added)."""
    if not args:
        print('Usage: dev.py branch <branch_name>')
        return
    branch_name = args[0]
    print('>>>> Creating branch {branch_name}')
    label = stash_if_any()
    subprocess.check_call(['git', 'clean', '-fd'])
    subprocess.check_call(['git', 'checkout', 'master'])
    subprocess.check_call(['git', 'pull'])
    subprocess.check_call(['git', 'checkout', '-b', branch_name])
    pop_if_any(label)

# If you try and git stash and then git stash pop when decksite is running locally you get in a mess.
# This cleans up for you. With the newer better behavior of --include-untracked this should now be unncessary.
@cli.command()
def popclean() -> None:
    print('>>>> Popping safely into messy directory.')
    try:
        subprocess.check_output(['git', 'stash', 'pop'], stderr=subprocess.STDOUT)
        return
    except subprocess.CalledProcessError as e:
        lines = e.output.decode().split('\n')
        already = [line.split(' ')[0] for line in lines if 'already' in line]
        for f in already:
            os.remove(f)
        subprocess.check_call(['git', 'stash', 'pop'])

def do_check(argv: List[str]) -> None:
    do_mypy(argv)
    do_lint()
    do_jslint(fix=False)

@cli.command()
@click.argument('argv', nargs=-1)
def check(argv: List[str]) -> None:
    do_check(argv)

def do_full_check(argv: List[str]) -> None:
    do_sort(False)
    do_check(argv)

# `full-check` differs from `check` in that it additionally checks import sorting.
# This is not strictly necessary because a bot will follow up any PR with another PR to correct import sorting.
# If you want to avoid that subsequent PR you can use `sort` and/or `full-check` to find import sorting issues.
# This adds 4s to the 18s run time of `check` on my laptop.
@cli.command()
@click.argument('argv', nargs=-1)
def full_check(argv: List[str]) -> None:
    do_full_check(argv)

@cli.command()
@click.argument('argv', nargs=-1)
def release(argv: List[str]) -> None:
    do_full_check([])
    do_safe_push([])
    do_pull_request(argv)

@cli.command()
def swagger() -> None:
    import decksite
    decksite.APP.config['SERVER_NAME'] = configuration.server_name()
    with decksite.APP.app_context():
        with open('decksite_api.yml', 'w') as f:
            f.write(json.dumps(decksite.APP.api.__schema__))


@cli.command()
def repip() -> None:
    """
    Sometimes, we need to pin to a dev commit of a dependency to fix a bug.
    This is a CI task to undo that when the next release lands
    """
    from importlib.metadata import version as _v

    import pipfile
    from packaging import version

    from shared import fetch_tools
    reqs = pipfile.load()
    default = reqs.data['default']
    for i in default.items():
        name: str = i[0]
        val: Union[str, dict] = i[1]
        if isinstance(val, dict) and 'git' in val.keys():
            print('> ' + repr(i))
            installed = version.Version(_v(name))
            info = fetch_tools.fetch_json(f'https://pypi.org/pypi/{name}/json')
            remote = version.Version(info['info']['version'])
            print(f'==\n{name}\nInstalled:\t{installed}\nPyPI:\t\t{remote}\n==')
            if remote > installed:
                pipenv = local['pipenv']
                try:
                    pipenv['install', f'{name}=={remote}'] & FG
                except ProcessExecutionError as e:
                    sys.exit(e.retcode)


if __name__ == '__main__':
    cli()
