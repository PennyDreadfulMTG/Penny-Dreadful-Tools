import os
import tempfile
from unittest.mock import patch

from babel.messages.catalog import TranslationError

from maintenance import validate_translations


def test_has_missing_var() -> None:
    english_s = '%(num)d victories'
    correct_s = '%(num)d побед'
    assert validate_translations.has_missing_var(english_s, correct_s) is None
    incorrect_s = '%(num) побед'
    assert validate_translations.has_missing_var(english_s, incorrect_s) is not None

def test_validate_pofile_handles_translation_error() -> None:
    # validate_pofile should not raise when read_po raises TranslationError
    content = b'msgid ""\nmsgstr ""\n'
    with tempfile.NamedTemporaryFile(suffix='.po', delete=False, mode='wb') as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        with patch('babel.messages.pofile.read_po', side_effect=TranslationError("unknown named placeholder 'num'")):
            validate_translations.validate_pofile(tmp_path)  # should not raise
    finally:
        os.unlink(tmp_path)

def test_ad_hoc_continues_after_error() -> None:
    # ad_hoc should process remaining files even if one raises
    calls = []
    def fake_validate(path: str) -> None:
        calls.append(path)
        if 'bad' in path:
            raise TranslationError("unknown named placeholder 'num'")

    with patch.object(validate_translations, 'validate_pofile', side_effect=fake_validate):
        with patch('os.walk', return_value=[('.', [], ['bad.po', 'good.po'])]):
            validate_translations.ad_hoc()

    assert len(calls) == 2
