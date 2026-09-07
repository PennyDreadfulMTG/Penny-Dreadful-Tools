from pathlib import Path

import dev


def test_find_files() -> None:
    assert dev.find_files('dtutil', 'py') == ['shared/dtutil.py', 'shared/dtutil_test.py']


def test_auth_decorators_must_be_innermost(tmp_path: Path) -> None:
    path = tmp_path / 'controllers.py'
    path.write_text("""\
@APP.route('/good-admin')
@auth.admin_required
def good_admin():
    pass

@auth.admin_required
@APP.route('/bad-admin')
def bad_admin():
    pass

@APP.route('/bad-demimod')
@auth.demimod_required
@fill_form('deck_id')
def bad_demimod():
    pass
""", encoding='utf-8')

    assert dev.auth_decorator_order_errors([str(path)]) == [
        f'{path}:6: PDA001 auth.admin_required must be the innermost decorator',
        f'{path}:12: PDA001 auth.demimod_required must be the innermost decorator',
    ]
