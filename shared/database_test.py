from shared.database import sqlescape


def test_sqlescape():
    assert sqlescape("There's an apostrophe.") == "There''s an apostrophe."
    assert sqlescape('a') == 'a'
    assert sqlescape(6) == 6
    assert sqlescape(6) != '6'
    assert sqlescape(6, force_string=True) == '6'
    assert sqlescape(6, force_string=True) != 6
