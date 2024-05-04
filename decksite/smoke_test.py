import pytest

from decksite.main import APP
from shared_web.smoke import SmokeTester

smoke_tester = SmokeTester(APP)

@pytest.mark.functional
def test() -> None:
    smoke_tester.run()

@pytest.mark.functional
def test_some_pages() -> None:
    for path in [
        '/', '/people/', '/cards/', '/cards/Unsummon/', '/competitions/', '/competitions/', '/tournaments/',
        '/resources/', '/bugs/', '/signup/', '/report/', '/admin/banners/',
    ]:
        smoke_tester.response_test(path, 200)
