import unittest

import pytest

from logsite import APP
from shared_web.smoke import SmokeTester


class LogsiteSmokeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tester: SmokeTester = SmokeTester(APP)

    @pytest.mark.functional
    def test_home(self) -> None:
        self.tester.data_test('/', '<h1><a href="/">PDBot Stats</a></h1>')

    @pytest.mark.functional
    def test_some_pages(self) -> None:
        for path in ['/', '/about/', '/matches/', '/people/', '/recent.json', '/stats.json']:
            self.tester.response_test(path, 200)
