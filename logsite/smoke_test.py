import unittest

import pytest

from logsite.main import APP


class SmokeTest(unittest.TestCase):
    def setUp(self):
        self.app = APP.test_client()
        # propagate the exceptions to the test client
        self.app.testing = True

    @pytest.mark.functional
    def test_home_status_code(self):
        result = self.app.get('/')
        self.assertEqual(result.status_code, 200)

    @pytest.mark.functional
    def test_home_data(self):
        result = self.app.get('/')
        self.assertIn('<h1><a href="/">PDBot Stats</a></h1>', result.data.decode('utf-8'))

    @pytest.mark.functional
    def test_some_pages(self):
        result = self.app.get('/')
        self.assertEqual(result.status_code, 200)
        result = self.app.get('/about/')
        self.assertEqual(result.status_code, 200)
        result = self.app.get('/matches/')
        self.assertEqual(result.status_code, 200)
        result = self.app.get('/people/')
        self.assertEqual(result.status_code, 200)
        result = self.app.get('/recent.json')
        self.assertEqual(result.status_code, 200)
