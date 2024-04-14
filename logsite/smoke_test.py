import pytest

from logsite import APP
from shared_web.smoke import SmokeTester


smoke_tester = SmokeTester(APP)

@pytest.mark.functional
def test():
    smoke_tester.run()

@pytest.mark.functional
def test_home() -> None:
    smoke_tester.data_test('/', '<h1><a href="/">PDBot Stats</a></h1>')

@pytest.mark.functional
def test_some_pages() -> None:
    for path in ['/', '/about/', '/matches/', '/people/', '/recent.json', '/stats.json']:
        smoke_tester.response_test(path, 200)
