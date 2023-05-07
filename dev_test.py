import dev


def test_find_files() -> None:
    assert dev.find_files('dtutil', 'py') == ['shared/dtutil.py', 'shared/dtutil_test.py']
