import pytest

from rotation_script import rotation_script


@pytest.mark.functional
def test_rotation() -> None:
    rotation_script.run()
