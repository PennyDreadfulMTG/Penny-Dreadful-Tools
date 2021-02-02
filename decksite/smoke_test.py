import unittest

import pytest

from decksite import APP
from shared import configuration
from shared_web.smoke import SmokeTester

APP.config['SERVER_NAME'] = configuration.server_name()

class DecksiteSmokeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tester: SmokeTester = SmokeTester(APP)

    @pytest.mark.functional
    def test_some_pages(self) -> None:
        for path in ['/', '/people/', '/cards/', '/cards/Unsummon/', '/competitions/', '/competitions/', '/tournaments/', '/resources/', '/bugs/', '/signup/', '/report/']:
            self.tester.response_test(path, 200)

    @pytest.mark.xfail(reason='We need to fix this')
    def test_trailing_slashes(self) -> None:
        with APP.app_context():
            for rule in self.tester.url_map.iter_rules():
                if 'GET' in rule.methods:
                    url = rule.rule
                    if not url.startswith('/api/') and rule.endpoint not in ['favicon', 'robots_txt']:
                        assert url.endswith('/')

    @pytest.mark.xfail(reason='We need to fix this')
    def test_api_no_trailing_slashes(self) -> None:
        with APP.app_context():
            for rule in self.tester.url_map.iter_rules():
                url = rule.rule
                if url.startswith('/api/'):
                    assert not url.endswith('/')
