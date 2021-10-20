#!/usr/bin/env python3
# pylint: disable=import-outside-toplevel
import json
import os
import subprocess
import sys
import time
from typing import Iterable, List, Optional, Tuple

import build as builddotpy
from shared import configuration
from shared.pd_exception import TestFailedException
from run import wait_for_db

try:
    import click
    from plumbum import FG, local
    from plumbum.commands.processes import ProcessExecutionError
except ImportError:
    sys.stderr.write('Please run ./build.py first\n')
    sys.exit(-1)


ON_PROD = configuration.get_bool('production')
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

@cli.command()
def lint() -> None:
    """
    Invoke Pylint with our preferred options
    """
    print('>>>> Running flake8')
    pipenv = local['pipenv']
    pipenv['run', 'flake8'] & FG  # noqa

@cli.command()
def stylefix() -> None:
    autopep = local['autopep8']
    autopep['--select', 'E123,E124,E261,E265,E303,E305,E306', '--in-place', '-r', '.'] & FG  # noqa

@cli.command()
@click.argument('argv', nargs=-1)
def mypy(argv: Tuple[str], strict: bool = False, typeshedding: bool = False) -> None:
    """
    Invoke mypy with our preferred options.
    Strict Mode enables additional checks that are currently failing (that we plan on integrating once they pass)
    """
    print('>>>> Typechecking')
    args = [
        '--show-error-codes',
        '--ignore-missing-imports',      # Don't complain about 3rd party libs with no stubs
        '--disallow-untyped-calls',      # Strict Mode.  All function calls must have a return type.
        '--warn-redundant-casts',
        '--disallow-incomplete-defs',    # All parameters must have type definitions.
        '--check-untyped-defs',          # Typecheck on all methods, not just typed ones.
        '--disallow-untyped-defs',       # All methods must be typed.
        '--strict-equality',             # Don't allow us to say "0" == 0 or other always false comparisons
        '--exclude=logsite_migrations',  # Exclude these generated files
        '--warn-unused-ignores',
    ]
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
    args.extend(argv or ['.'])  # Invoke on the entire project.
    # pylint: disable=import-outside-toplevel
    from mypy import api
    result = api.run(args)
    if result[0]:
        print(result[0])  # stdout
    if result[1]:
        sys.stderr.write(result[1])  # stderr
    print('Exit status: {code} ({english})'.format(code=result[2], english='Failure' if result[2] else 'Success'))
    if result[2]:
        raise TestFailedException(result[2])

@cli.command()
@click.argument('argv', nargs=-1)
def unit(argv: Tuple[str]) -> None:
    runtests(argv, 'not functional and not perf', True)

@cli.command()
@click.argument('argv', nargs=-1)
def test(argv: Tuple[str]) -> None:
    runtests(argv, '', False)

def runtests(argv: Iterable[str], m: str, mark: bool) -> None:
    """
    Literally just prepare the DB and then invoke pytest.
    """
    args = list(argv)
    if mark:
        if args and not args[0].startswith('-'):
            to_find = args.pop(0)
            args.extend(find_files(to_find, 'py'))
        args.extend(['-x', '-m', m])

    argstr = ' '.join(args)
    print(f'>>>> Running tests with "{argstr}"')
    # pylint: disable=import-outside-toplevel
    import pytest

    from magic import fetcher, multiverse, oracle, whoosh_write
    if multiverse.init():
        whoosh_write.reindex()
    oracle.init()
    try:
        fetcher.sitemap()
    except fetcher.FetchException:
        print(f'Config was pointed at {fetcher.decksite_url()}, but it doesnt appear to be listening.')
        for k in ['decksite_hostname', 'decksite_port', 'decksite_protocol']:
            configuration.CONFIG[k] = configuration.DEFAULTS[k]

    code = pytest.main(args)
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        upload_coverage()
    sys.exit(code)

# pylint: disable=pointless-statement
@cli.command()
def upload_coverage() -> None:
    try:
        print('>>>> Upload coverage')
        # pylint: disable=import-outside-toplevel
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

# pylint: disable=import-outside-toplevel
@cli.command()
@click.option('--fix', is_flag=True, default=False)
def sort(fix: bool = False) -> None:
    print('>>>> Checking imports')
    if fix:
        subprocess.check_call(['isort', '.'])
    else:
        subprocess.check_call(['isort', '.', '--check'])

# pylint: disable=import-outside-toplevel
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
@click.argument('argv', nargs=-1)
def safe_push(args: List[str]) -> None:
    label = stash_if_any()
    print('>>>> Rebasing branch on master')
    subprocess.check_call(['git', 'pull', 'origin', 'master', '--rebase'])
    unit(args)
    push()
    pop_if_any(label)

@cli.command()
def push() -> None:
    print('>>>> Pushing')
    branch_name = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).strip().decode()
    subprocess.check_call(['git', 'push', '--set-upstream', 'origin', branch_name])

@cli.command()
@click.argument('argv', nargs=-1)
def pull_request(argv: Tuple[str]) -> None:
    print('>>>> Pull request')
    try:
        subprocess.check_call(['gh', 'pr', 'create'])
    except (subprocess.CalledProcessError, FileNotFoundError):
        subprocess.check_call(['hub', 'pull-request', *argv])

@cli.command()
@click.option('--fix', is_flag=True, default=False)
def jslint(fix: bool = False) -> None:
    print('>>>> Linting javascript')
    files = find_files(file_extension='js', exclude=['.eslintrc.js', 'shared_web/static/js/tipped.min.js']) + find_files(file_extension='jsx')
    cmd = [os.path.join('.', 'node_modules', '.bin', 'eslint')]
    if fix:
        cmd.append('--fix')
    subprocess.check_call(cmd + files, shell=ON_WINDOWS)

@cli.command()
def jsfix() -> None:
    print('>>>> Fixing js')
    jslint(fix=True)

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

@cli.command()
@click.argument('argv', nargs=-1)
def check(args: List[str]) -> None:
    sort()
    mypy(args)
    lint(args)
    jslint()

@cli.command()
@click.argument('argv', nargs=-1)
def release(args: List[str]) -> None:
    check([])
    safe_push([])
    pull_request(args)

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


@cli.command()
def check_requirements() -> None:
    files = find_files(file_extension='py')
    r = subprocess.call([sys.executable, '-X', 'utf-8', '-m', 'pip_check_reqs.find_extra_reqs'] + files)
    r = subprocess.call([sys.executable, '-X', 'utf-8', '-m', 'pip_check_reqs.find_missing_reqs'] + files) or r

@cli.command()
def swagger() -> None:
    import decksite
    decksite.APP.config['SERVER_NAME'] = configuration.server_name()
    with decksite.APP.app_context():
        with open('decksite_api.yml', 'w') as f:
            f.write(json.dumps(decksite.APP.api.__schema__))


if __name__ == '__main__':
    cli()
