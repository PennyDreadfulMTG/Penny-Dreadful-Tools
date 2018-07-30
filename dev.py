import os
import sys

from shared import configuration

LINT_PATHS = [o for o in os.listdir('.') if os.path.isdir(o) and os.path.exists(os.path.join(o, '__init__.py'))]
LINT_PATHS.extend([o for o in os.listdir('.') if os.path.isfile(o) and os.path.splitext(o)[1] == '.py'])

ON_PROD = configuration.get_bool('production')
if ON_PROD:
    print('DO NOT RUN dev.py ON PROD')
    sys.exit(1)

def run() -> None:
    cmd = sys.argv[1].lower()

    if cmd in ('lint', 'pylint'):
        lint()

    elif cmd in ('types', 'mypy'):
        mypy()

    elif cmd in ('test', 'tests', 'pytest'):
        tests()

    elif cmd in ('nuke_db', 'reset_db'):
        reset_db()

    else:
        print('Unrecognised command {cmd}.'.format(cmd=cmd))
        exit(1)

def lint() -> None:
    args = ['--rcfile=.pylintrc', # Load rcfile first.
            '--ignored-modules=alembic,MySQLdb,flask_sqlalchemy,distutils.dist', # override ignored-modules (codacy hack)
            '--load-plugins', 'pylint_quotes, pylint_monolith', # Plugins
            '--reports=n', # Don't show reports.
            '-f', 'parseable', # Machine-readable output.
            '-j', '4' # Use four cores for speed.
           ]
    args.extend(sys.argv[2:] or LINT_PATHS)
    import pylint.lint
    pylint.lint.Run(args, do_exit=True)

def mypy() -> None:
    args = [
        '--ignore-missing-imports',     # Don't complain about 3rd party libs with no stubs
        '--disallow-untyped-calls',     # Strict Mode.  All function calls must have a return type.
        # "--disallow-incomplete-defs", # All parameters must have type definitions.
        ]
    args.extend(sys.argv[2:] or [
        '.'                             # Invoke on the entire project.
        ])
    from mypy import api
    result = api.run(args)

    if result[0]:
        print(result[0])  # stdout

    if result[1]:
        print(result[1])  # stderr

    print('Exit status: {code} ({english})'.format(code=result[2], english='Failure' if result[2] else 'Success'))
    sys.exit(result[2])

def tests() -> None:
    import pytest
    from magic import multiverse, oracle
    multiverse.init()
    oracle.init()
    code = pytest.main(sys.argv[2:])
    sys.exit(code)

def reset_db() -> None:
    """
    Handle with care.
    """
    import decksite.database
    decksite.database.db().nuke_database()
    import magic.database
    magic.database.db().nuke_database()

if __name__ == '__main__':
    run()
