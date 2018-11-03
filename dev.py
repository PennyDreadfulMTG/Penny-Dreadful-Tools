import os
import subprocess
import sys
from typing import List

from shared import configuration

LINT_PATHS = [o for o in os.listdir('.') if os.path.isdir(o) and os.path.exists(os.path.join(o, '__init__.py'))]
LINT_PATHS.extend([o for o in os.listdir('.') if os.path.isfile(o) and os.path.splitext(o)[1] == '.py'])

ON_PROD = configuration.get_bool('production')
if ON_PROD:
    print('DO NOT RUN dev.py ON PROD')
    sys.exit(1)

def run() -> None:
    cmd = sys.argv[1].lower()
    args = sys.argv[2:]

    if cmd in ('lint', 'pylint'):
        lint(args)

    elif cmd in ('types', 'mypy'):
        mypy(args)

    elif cmd == 'mypy-strict':
        mypy(args, True)

    elif cmd in ('test', 'tests', 'pytest'):
        tests(args)

    elif cmd in ('nuke_db', 'reset_db'):
        reset_db()

    elif cmd == 'push':
        push()

    elif cmd in ('imports', 'isort', 'sort'):
        sort()

    elif cmd in ('fix-sorts', 'fix-imports', 'fiximports'):
        sort(True)

    elif cmd in ('pr', 'pull-request'):
        pull_request(args)

    elif cmd == 'release':
        push()
        pull_request(args)


    else:
        print('Unrecognised command {cmd}.'.format(cmd=cmd))
        exit(1)

def lint(argv: List[str]) -> None:
    args = ['--rcfile=.pylintrc', # Load rcfile first.
            '--ignored-modules=alembic,MySQLdb,flask_sqlalchemy,distutils.dist', # override ignored-modules (codacy hack)
            '--load-plugins', 'pylint_quotes, pylint_monolith', # Plugins
            '--reports=n', # Don't show reports.
            '-f', 'parseable', # Machine-readable output.
            '-j', '4' # Use four cores for speed.
           ]
    args.extend(argv or LINT_PATHS)
    import pylint.lint
    linter = pylint.lint.Run(args, do_exit=False)
    if linter.linter.msg_status:
        sys.exit(linter.linter.msg_status)

def mypy(argv: List[str], strict: bool = False) -> None:
    args = [
        '--ignore-missing-imports',     # Don't complain about 3rd party libs with no stubs
        '--disallow-untyped-calls',     # Strict Mode.  All function calls must have a return type.
        ]
    if strict:
        args.append('--disallow-incomplete-defs') # All parameters must have type definitions.
    args.extend(argv or [
        '.'                             # Invoke on the entire project.
        ])
    from mypy import api
    result = api.run(args)

    if result[0]:
        print(result[0])  # stdout

    if result[1]:
        sys.stderr.write(result[1])  # stderr

    print('Exit status: {code} ({english})'.format(code=result[2], english='Failure' if result[2] else 'Success'))
    if result[2]:
        n = len(result[0].split('\n'))
        print(f'{n} issues')
        sys.exit(result[2])

def tests(argv: List[str]) -> None:
    import pytest
    from magic import multiverse, oracle
    multiverse.init()
    oracle.init()
    code = pytest.main(argv)
    if code:
        sys.exit(code)

def sort(fix: bool = False) -> None:
    from isort import SortImports
    import isort.main
    config = isort.main.from_path('.')
    if fix:
        config['recursive'] = True
        config['check'] = False
        config['ask_to_apply'] = False
    else:
        config['check'] = True

    file_names = isort.main.iter_source_code(['.'], config, [])
    wrong_sorted_files = False
    for file_name in file_names:
        try:
            sort_attempt = SortImports(file_name, check=config['check'])
            incorrectly_sorted = sort_attempt.incorrectly_sorted
            if incorrectly_sorted:
                wrong_sorted_files = True
        except IOError as e:
            print('WARNING: Unable to parse file {0} due to {1}'.format(file_name, e))
    if wrong_sorted_files:
        sys.exit(2)

def reset_db() -> None:
    """
    Handle with care.
    """
    import decksite.database
    decksite.database.db().nuke_database()
    import magic.database
    magic.database.db().nuke_database()

def push() -> None:
    subprocess.check_call(['git', 'pull', 'origin', 'master', '--rebase'])
    lint([])
    mypy([], False)
    tests([])
    sort(fix=False)
    branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).strip().decode()
    subprocess.check_call(['git', 'push', '--set-upstream', 'origin', branch])

def pull_request(argv: List[str]) -> None:
    subprocess.check_call(['hub', 'pull-request', *argv])

if __name__ == '__main__':
    run()
