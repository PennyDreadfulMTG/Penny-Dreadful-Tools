import unittest

import pytest

from decksite.main import APP
from shared_web.smoke import Tester


class DecksiteSmokeTest(unittest.TestCase):
    def setUp(self):
        self.tester: Tester = Tester(APP)

    @pytest.mark.functional
    def test_base(self) -> None:
        self.tester.base_tests()

    @pytest.mark.functional
    def test_home(self) -> None:
        self.tester.data_test('/', '<h1><string>Latest Decks</string></h1>')

    @pytest.mark.functional
    def test_some_pages(self) -> None:
        for path in ['/', '/people/', '/cards/', '/cards/Unsummon/', '/competitions/', '/competitions/', '/tournaments/', '/resources/', '/bugs/', '/signup/', '/report/']:
            self.tester.response_test(path, 200)
