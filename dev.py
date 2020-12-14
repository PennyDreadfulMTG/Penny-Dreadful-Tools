#!/usr/bin/env python3
# pylint: disable=import-outside-toplevel
import json
import os
import subprocess
import sys
import time
from pickle import PicklingError
from typing import List, Optional

from shared import configuration
from shared.pd_exception import InvalidArgumentException, TestFailedException

try:
    from plumbum import FG, local
    from plumbum.commands.processes import ProcessExecutionError
except ImportError:
    sys.stderr.write('Please run ./dev.py build\n')
    ProcessExecutionError = subprocess.CalledProcessError


ON_PROD = configuration.get_bool('production')
if ON_PROD:
    sys.stderr.write('DO NOT RUN dev.py ON PROD\n')
    sys.exit(1)

ON_WINDOWS = sys.platform == 'win32'

def run() -> None:
    try:
        try:
            exit_code = None
            run_dangerously()
        except InvalidArgumentException:
            exit_code = 1
            raise
        except TestFailedException:
            exit_code = 2
            raise
        except ProcessExecutionError:
            exit_code = 3
            raise
    except Exception as e: # pylint: disable=broad-except
        msg = type(e).__name__ + ' running ' + str(sys.argv) + ': ' + ' [' + str(e.args) + '] ' + str(e) + '\n'
        sys.stderr.write(msg)
        if not exit_code:
            raise
        sys.exit(exit_code if exit_code else 4)

def run_dangerously() -> None:
    try:
        cmd = sys.argv[1].lower()
        args = sys.argv[2:]
    except IndexError as e:
        raise InvalidArgumentException('Please supply an argument.') from e
    if cmd == 'unit':
        unit(args)
    elif cmd == 'functional':
        runtests(args, 'functional', True)
    elif cmd == 'perf':
        runtests(args, 'perf', True)
    elif cmd in ('test', 'tests'):
        runtests(args, '', False)
    elif cmd in ('lint', 'pylint'):
        lint(args)
    elif cmd in ('types', 'mypy'):
        mypy(args)
    elif cmd == 'mypy-strict':
        mypy(args, strict=True)
    elif cmd == 'typeshed':
        mypy(args, typeshedding=True)
    elif cmd == 'jslint':
        jslint()
    elif cmd == 'jsfix':
        jsfix()
    elif cmd in ('nuke_db', 'reset_db'):
        reset_db()
    elif cmd in ('imports', 'isort', 'sort'):
        sort()
    elif cmd in ('fix-sorts', 'fix-imports', 'fiximports'):
        sort(True)
    elif cmd in ('pr', 'pull-request'):
        pull_request(args)
    elif cmd == 'build':
        build()
    elif cmd == 'buildjs':
        buildjs()
    elif cmd == 'popclean':
        popclean()
    elif cmd == 'readme':
        from generate_readme import generate_readme
        generate_readme()
    elif cmd == 'coverage':
        coverage()
    elif cmd == 'watch':
        watch()
    elif cmd == 'branch':
        branch(args)
    elif cmd == 'push':
        push()
    elif cmd == 'check':
        check(args)
    elif cmd in ('safe_push', 'safepush'):
        safe_push(args)
    elif cmd == 'release':
        release(args)
    elif cmd == 'check-reqs':
        check_requirements()
    elif cmd == 'swagger':
        swagger()
    else:
        raise InvalidArgumentException('Unrecognised command {cmd}.'.format(cmd=cmd))

def lint(argv: List[str]) -> None:
    """
    Invoke Pylint with our preferred options
    """
    print('>>>> Running pylint')
    args = ['--rcfile=.pylintrc', # Load rcfile first.
            '--ignored-modules=alembic,MySQLdb,flask_sqlalchemy,distutils.dist', # override ignored-modules (codacy hack)
            '--load-plugins', 'pylint_quotes,pylint_monolith', # Plugins
            '-f', 'parseable', # Machine-readable output.
            '-j', str(configuration.get_int('pylint_threads')), # Use four cores for speed.
           ]
    args.extend(argv or find_files(file_extension='py'))
    # pylint: disable=import-outside-toplevel
    import pylint.lint
    try:
        linter = pylint.lint.Run(args, exit=False)
    except (PicklingError, RecursionError):
        print('Error while running pylint with multiprocessing')
        configuration.write('pylint_threads', 1)
        lint(argv)
        return

    if linter.linter.msg_status:
        raise TestFailedException(linter.linter.msg_status)

def mypy(argv: List[str], strict: bool = False, typeshedding: bool = False) -> None:
    """
    Invoke mypy with our preferred options.
    Strict Mode enables additional checks that are currently failing (that we plan on integrating once they pass)
    """
    print('>>>> Typechecking')
    args = [
        '--show-error-codes',
        '--ignore-missing-imports',     # Don't complain about 3rd party libs with no stubs
        '--disallow-untyped-calls',     # Strict Mode.  All function calls must have a return type.
        '--warn-redundant-casts',
        '--disallow-incomplete-defs',   # All parameters must have type definitions.
        '--check-untyped-defs',         # Typecheck on all methods, not just typed ones.
        '--disallow-untyped-defs',      # All methods must be typed.
        '--strict-equality',        # Don't allow us to say "0" == 0 or other always false comparisons
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
    args.extend(argv or ['.']) # Invoke on the entire project.
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

def unit(argv: List[str]) -> None:
    runtests(argv, 'not functional and not perf', True)

def runtests(argv: List[str], m: str, mark: bool) -> None:
    """
    Literally just prepare the DB and then invoke pytest.
    """
    args = argv.copy()
    if mark:
        if args and not args[0].startswith('-'):
            to_find = args.pop(0)
            args.extend(find_files(to_find, 'py'))
        args.extend(['-x', '-m', m])

    argstr = ' '.join(args)
    print(f'>>>> Running tests with "{argstr}"')
    # pylint: disable=import-outside-toplevel
    import pytest

    from magic import fetcher, multiverse, oracle
    multiverse.init()
    oracle.init()
    try:
        fetcher.sitemap()
    except fetcher.FetchException:
        print(f'Config was pointed at {fetcher.decksite_url()}, but it doesnt appear to be listening.')
        for k in ['decksite_hostname', 'decksite_port', 'decksite_protocol']:
            configuration.CONFIG[k] = configuration.DEFAULTS[k]

    code = pytest.main(args)
    if os.environ.get('TRAVIS') == 'true':
        upload_coverage()
    if code:
        raise TestFailedException(code)

# pylint: disable=pointless-statement
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
def sort(fix: bool = False) -> None:
    print('>>>> Checking imports')
    if fix:
        subprocess.check_call(['isort', '.'])
    else:
        subprocess.check_call(['isort', '.', '--check'])

# pylint: disable=import-outside-toplevel
def reset_db() -> None:
    """
    Handle with care.
    """
    print('>>>> Reset db')
    import decksite.database
    decksite.database.db().nuke_database()
    import magic.database
    magic.database.db().nuke_database()

def safe_push(args: List[str]) -> None:
    label = stash_if_any()
    print('>>>> Rebasing branch on Master')
    subprocess.check_call(['git', 'pull', 'origin', 'master', '--rebase'])
    unit(args)
    push()
    pop_if_any(label)

def push() -> None:
    print('>>>> Pushing')
    branch_name = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).strip().decode()
    subprocess.check_call(['git', 'push', '--set-upstream', 'origin', branch_name])

def pull_request(argv: List[str]) -> None:
    print('>>>> Pull request')
    try:
        subprocess.check_call(['gh', 'pr', 'create'])
    except (subprocess.CalledProcessError, FileNotFoundError):
        subprocess.check_call(['hub', 'pull-request', *argv])

def build() -> None:
    print('>>>> Installing Requirements')
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pipenv'])
    pipargs = ['pipenv', 'sync']
    if sys.prefix == sys.base_prefix:
        pipargs = [sys.executable, '-m', 'pipenv', 'install', '--system']
    subprocess.check_call(pipargs)
    print('>>>> Installing node modules')
    subprocess.check_call(['npm', 'install'], shell=ON_WINDOWS)
    buildjs()

def buildjs() -> None:
    print('>>>> Building javascript')
    subprocess.check_call(['npm', 'run-script', 'build'], shell=ON_WINDOWS)

def jslint(fix: bool = False) -> None:
    print('>>>> Linting javascript')
    files = find_files(file_extension='js', exclude=['.eslintrc.js', 'shared_web/static/js/tipped.min.js']) + find_files(file_extension='jsx')
    cmd = [os.path.join('.', 'node_modules', '.bin', 'eslint')]
    if fix:
        cmd.append('--fix')
    subprocess.check_call(cmd + files, shell=ON_WINDOWS)

def jsfix() -> None:
    print('>>>> Fixing js')
    jslint(fix=True)

def coverage() -> None:
    print('>>>> Coverage')
    subprocess.check_call(['coverage', 'run', 'dev.py', 'tests'])
    subprocess.check_call(['coverage', 'xml'])
    subprocess.check_call(['coverage', 'report'])

def watch() -> None:
    print('>>>> Watching')
    subprocess.check_call(['npm', 'run', 'watch'], shell=ON_WINDOWS)

# Make a branch based off of current (remote) master with all your local changes preserved (but not added).
def branch(args: List[str]) -> None:
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

def check(args: List[str]) -> None:
    sort()
    mypy(args)
    lint(args)
    jslint()

def release(args: List[str]) -> None:
    check([])
    safe_push([])
    pull_request(args)

def find_files(needle: str = '', file_extension: str = '', exclude: Optional[List[str]] = None)  -> List[str]:
    paths = subprocess.check_output(['git', 'ls-files']).strip().decode().split('\n')
    paths = [p for p in paths if 'logsite_migrations' not in p]
    if file_extension:
        paths = [p for p in paths if p.endswith(file_extension)]
    if needle:
        paths = [p for p in paths if needle in os.path.basename(p)]
    if exclude:
        paths = [p for p in paths if p not in exclude]
    return paths


def check_requirements() -> None:
    files = find_files(file_extension='py')
    r = subprocess.call([sys.executable, '-X', 'utf-8', '-m', 'pip_check_reqs.find_extra_reqs'] + files)
    r = subprocess.call([sys.executable, '-X', 'utf-8', '-m', 'pip_check_reqs.find_missing_reqs'] + files) or r

def swagger() -> None:
    import decksite
    decksite.APP.config['SERVER_NAME'] = configuration.server_name()
    with decksite.APP.app_context():
        with open('decksite_api.yml', 'w') as f:
            f.write(json.dumps(decksite.APP.api.__schema__))

if __name__ == '__main__':
    run()
