from pathlib import Path

import pytest

from shared import settings


def test_named_environment_variable_is_not_logged_or_persisted(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    key = 'test_named_environment_variable'
    environment_variable = 'PDT_TEST_NAMED_ENVIRONMENT_VARIABLE'
    setting = settings.StrSetting(key, '', environment_variable=environment_variable)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setitem(settings.CONFIG, key, 'cached-value')
    monkeypatch.setenv(environment_variable, 'secret-value')

    assert setting.value == 'secret-value'
    assert capsys.readouterr().out == ''
    assert not (tmp_path / 'config.json').exists()
