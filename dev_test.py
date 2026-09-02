import textwrap
from pathlib import Path

import dev
import lint_auth_ordering


def test_find_files() -> None:
    assert dev.find_files('dtutil', 'py') == ['shared/dtutil.py', 'shared/dtutil_test.py']


def test_lint_auth_ordering_catches_violation(tmp_path: Path) -> None:
    bad = tmp_path / 'bad.py'
    bad.write_text(textwrap.dedent("""
        from decksite import auth
        from shared_web.decorators import fill_form

        @auth.admin_required
        @fill_form('x')
        def my_view(x=None):
            pass
    """))
    errors = lint_auth_ordering.check_file(bad)
    assert len(errors) == 1
    assert 'admin_required' in errors[0]
    assert 'my_view' in errors[0]


def test_lint_auth_ordering_passes_when_last(tmp_path: Path) -> None:
    good = tmp_path / 'good.py'
    good.write_text(textwrap.dedent("""
        from decksite import auth
        from shared_web.decorators import fill_form

        @fill_form('x')
        @auth.admin_required
        def my_view(x=None):
            pass
    """))
    errors = lint_auth_ordering.check_file(good)
    assert errors == []


def test_lint_auth_ordering_ignores_unrelated_decorators(tmp_path: Path) -> None:
    unrelated = tmp_path / 'unrelated.py'
    unrelated.write_text(textwrap.dedent("""
        import functools

        def my_decorator(f):
            @functools.wraps(f)
            def wrapper(*args, **kwargs):
                return f(*args, **kwargs)
            return wrapper

        @my_decorator
        def some_view():
            pass
    """))
    errors = lint_auth_ordering.check_file(unrelated)
    assert errors == []
