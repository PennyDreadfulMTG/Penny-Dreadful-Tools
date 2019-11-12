from shared.database import sqlescape
from shared.pd_exception import InvalidArgumentException


def test_sqlescape() -> None:
    assert sqlescape("There's an apostrophe.") == "'There''s an apostrophe.'"
    assert sqlescape('a') == "'a'"
    assert sqlescape(6) == 6
    assert sqlescape(6) != '6'
    assert sqlescape(6, force_string=True) == "'6'"
    assert sqlescape(6, force_string=True) != 6
    assert sqlescape('this\\one') == "'this\\\\one'"
    found = False
    try:
        sqlescape({})
    except InvalidArgumentException:
        found = True
    assert found
