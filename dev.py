#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time
from typing import Iterable, List, Optional

import build as builddotpy
from run import wait_for_db
from shared import configuration
from shared.pd_exception import TestFailedException

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

@cli.command()
def lint() -> None:
    do_lint()

def do_lint() -> None:
    """
    Invoke Pylint with our preferred options
    """
    print('>>>> Running flake8')
    pipenv = local['pipenv']
    try:
        pipenv['run', 'python', '-m', 'flake8'] & FG  # noqa
    except ProcessExecutionError as e:
        sys.exit(e.retcode)


@cli.command()
def stylefix() -> None:
    autopep = local['autopep8']
    autopep['--select', 'E123,E124,E261,E265,E303,E305,E306', '--in-place', '-r', '.'] & FG  # noqa

@cli.command()
@click.argument('argv', nargs=-1)
def mypy(argv: List[str], strict: bool = False, typeshedding: bool = False) -> None:
    do_mypy(argv, strict, typeshedding)

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
        raise TestFailedException(result[2])

@cli.command()
@click.argument('argv', nargs=-1)
def unit(argv: List[str]) -> None:
    do_unit(argv)

def do_unit(argv: List[str]) -> None:
    runtests(argv, 'not functional and not perf', True)

@cli.command()
@click.argument('argv', nargs=-1)
def test(argv: List[str]) -> None:
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
    import pytest

    code = pytest.main(args)
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        upload_coverage()
    if code:
        sys.exit(code)

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

@cli.command()
@click.option('--fix', is_flag=True, default=False)
def sort(fix: bool = False) -> None:
    do_sort(fix)

def do_sort(fix: bool) -> None:
    print('>>>> Checking imports')
    pipenv = local['pipenv']
    if fix:
        pipenv['run', 'isort', '.'] & FG  # noqa
    else:
        pipenv['run', 'isort', '.', '--check'] & FG  # noqa

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
def safe_push(argv: List[str]) -> None:
    do_safe_push(argv)

def do_safe_push(argv: List[str]) -> None:
    label = stash_if_any()
    print('>>>> Rebasing branch on master')
    subprocess.check_call(['git', 'pull', 'origin', 'master', '--rebase'])
    do_unit(argv)
    do_push()
    pop_if_any(label)

@cli.command()
def push() -> None:
    do_push()

def do_push() -> None:
    print('>>>> Pushing')
    branch_name = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).strip().decode()
    subprocess.check_call(['git', 'push', '--set-upstream', 'origin', branch_name])

@cli.command()
@click.argument('argv', nargs=-1)
def pull_request(argv: List[str]) -> None:
    do_pull_request(argv)

def do_pull_request(argv: List[str]) -> None:
    print('>>>> Pull request')
    try:
        subprocess.check_call(['hub', 'pull-request', *argv])
    except (subprocess.CalledProcessError, FileNotFoundError):
        subprocess.check_call(['gh', 'pr', 'create'])

@cli.command()
@click.option('--fix', is_flag=True, default=False)
def jslint(fix: bool = False) -> None:
    do_jslint(fix)

def do_jslint(fix: bool) -> None:
    print('>>>> Linting javascript')
    files = find_files(file_extension='js', exclude=['.eslintrc.js', 'shared_web/static/js/tipped.min.js']) + find_files(file_extension='jsx')
    cmd = [os.path.join('.', 'node_modules', '.bin', 'eslint')]
    if fix:
        cmd.append('--fix')
    subprocess.check_call(cmd + files, shell=ON_WINDOWS)

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
def check(argv: List[str]) -> None:
    do_check(argv)

def do_check(argv: List[str]) -> None:
    do_mypy(argv)
    do_lint()
    do_jslint(fix=False)

# `full-check` differs from `check` in that it additionally checks import sorting.
# This is not strictly necessary because a bot will follow up any PR with another PR to correct import sorting.
# If you want to avoid that subsequent PR you can use `sort` and/or `full-check` to find import sorting issues.
# This adds 4s to the 18s run time of `check` on my laptop.
@cli.command()
@click.argument('argv', nargs=-1)
def full_check(argv: List[str]) -> None:
    do_full_check(argv)

def do_full_check(argv: List[str]) -> None:
    do_sort(False)
    do_check(argv)

@cli.command()
@click.argument('argv', nargs=-1)
def release(argv: List[str]) -> None:
    do_full_check([])
    do_safe_push([])
    do_pull_request(argv)

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
def swagger() -> None:
    import decksite
    decksite.APP.config['SERVER_NAME'] = configuration.server_name()
    with decksite.APP.app_context():
        with open('decksite_api.yml', 'w') as f:
            f.write(json.dumps(decksite.APP.api.__schema__))


if __name__ == '__main__':
    cli()
