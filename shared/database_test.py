import pytest

from shared.database import sqlescape, sqllikeescape
from shared.pd_exception import InvalidArgumentException


def test_sqlescape() -> None:
    assert sqlescape("There's an apostrophe.") == "'There''s an apostrophe.'"
    assert sqlescape('a') == "'a'"
    assert sqlescape(6) == 6
    assert sqlescape(6) != '6'
    assert sqlescape(6, force_string=True) == "'6'"
    assert sqlescape(6, force_string=True) != 6
    assert sqlescape('this\\one') == "'this\\\\one'"
    with pytest.raises(InvalidArgumentException):
        sqlescape({})


def test_sqllikeescape() -> None:
    assert sqllikeescape('a') == "'%%a%%'"
    with pytest.raises(InvalidArgumentException):
        sqllikeescape(6)  # type: ignore
    assert sqllikeescape('this\\one') == "'%%this\\\\one%%'"
    assert sqllikeescape('%') == "'%%\\%%%%'"
    with pytest.raises(InvalidArgumentException):
        sqllikeescape({})  # type: ignore
    hard = r'What % _chance_ of a \?'
    assert sqllikeescape(hard) == r"'%%What \%% \_chance\_ of a \\?%%'"
    assert sqllikeescape(hard, fuzzy=True) == r"'%%W%%h%%a%%t%% %%\%%%% %%\_%%c%%h%%a%%n%%c%%e%%\_%% %%o%%f%% %%a%% %%\\%%?%%'"
