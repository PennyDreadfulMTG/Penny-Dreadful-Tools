import unittest

import pytest

from logsite.main import APP
from shared_web.smoke import Tester


class LogsiteSmokeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tester: Tester = Tester(APP)

    @pytest.mark.functional
    def test_base(self) -> None:
        self.tester.base_tests()

    @pytest.mark.functional
    def test_home(self) -> None:
        self.tester.data_test('/', '<h1><a href="/">PDBot Stats</a></h1>')

    @pytest.mark.functional
    def test_some_pages(self) -> None:
        for path in ['/', '/about/', '/matches/', '/people/', '/recent.json', '/stats.json']:
            self.tester.response_test(path, 200)
