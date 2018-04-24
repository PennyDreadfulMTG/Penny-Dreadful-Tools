import os
import sys

LINT_PATHS = [o for o in os.listdir('.') if os.path.isdir(o) and os.path.exists(os.path.join(o, '__init__.py'))]
LINT_PATHS.extend([o for o in os.listdir('.') if os.path.isfile(o) and os.path.splitext(o)[1] == '.py'])

def run() -> None:
    cmd = sys.argv[1].lower()

    if cmd in ('lint', 'pylint'):
        lint()

def lint() -> None:
    args = sys.argv[2:] or ['--rcfile=.pylintrc', # Load rcfile first.
                            '--ignored-modules=alembic,MySQLdb,flask_sqlalchemy', # override ignored-modules (codacy hack)
                            '--reports=n', '-f', 'parseable'
                           ]
    args.extend(LINT_PATHS)
    import pylint.lint
    pylint.lint.Run(args)

if __name__ == '__main__':
    run()
