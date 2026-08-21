import logging

import pytest

from discordbot import error_handling


def make_error(message: str) -> Exception:
    try:
        raise ValueError(message)
    except ValueError as e:
        return e


def test_same_error_has_same_code() -> None:
    assert error_handling.error_code(make_error('broken')) == error_handling.error_code(make_error('broken'))


def test_different_errors_have_different_codes() -> None:
    assert error_handling.error_code(make_error('first')) != error_handling.error_code(make_error('second'))


def test_public_message_is_short_and_one_line() -> None:
    message = error_handling.public_message(make_error('broken'), 'first line\n' + ('x' * 300))

    assert '\n' not in message
    assert len(message) <= error_handling.MAX_PUBLIC_ERROR_LENGTH
    assert 'Error code' in message
    assert error_handling.LOG_FILE in message
    assert f'`{error_handling.LOG_FILE}`' in message


def test_public_message_derives_hint_from_exception() -> None:
    message = error_handling.public_message(make_error('broken\ntechnical detail'))

    assert 'Hint: `ValueError: broken`.' in message
    assert 'technical detail' not in message


def test_log_exception_includes_traceback_but_redacts_secrets(caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(error_handling.repo, 'REDACTED_STRINGS', {'secret'})
    error = make_error('secret')

    with caplog.at_level(logging.ERROR):
        error_handling.log_exception(error, 'Command failed')

    assert 'Traceback' in caplog.text
    assert 'secret' not in caplog.text
    assert 'REDACTED' in caplog.text
