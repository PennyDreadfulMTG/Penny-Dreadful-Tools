import unittest
from flask.helpers import url_for

import pytest

from decksite import APP
from shared_web.smoke import SmokeTester


class DecksiteSmokeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tester: SmokeTester = SmokeTester(APP)

    @pytest.mark.functional
    def test_some_pages(self) -> None:
        for path in ['/', '/people/', '/cards/', '/cards/Unsummon/', '/competitions/', '/competitions/', '/tournaments/', '/resources/', '/bugs/', '/signup/', '/report/']:
            self.tester.response_test(path, 200)

    def test_trailing_slashes(self) -> None:
        urls = [url_for(rule.endpoint) for rule in APP.url_map.iter_rules()]
        for url in urls:
            if not url.startswith('/api/'):
                assert url.endswith('/')

    @pytest.mark.xfail('We need to fix this')
    def test_api_no_trailing_slashes(self) -> None:
        urls = [url_for(rule.endpoint) for rule in APP.url_map.iter_rules()]
        for rule in APP.url_map.iter_rules():
            if url.startswith('/api/'):
                assert not url.endswith('/')
