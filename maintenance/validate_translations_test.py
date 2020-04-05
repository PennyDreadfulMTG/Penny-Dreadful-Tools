from maintenance import validate_translations


def test_has_missing_var() -> None:
    english_s = '%(num)d victories'
    correct_s = '%(num)d побед'
    assert validate_translations.has_missing_var(english_s, correct_s) is None
    incorrect_s = '%(num) побед'
    assert validate_translations.has_missing_var(english_s, incorrect_s) is not None
