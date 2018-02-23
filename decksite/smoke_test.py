import unittest

import pytest

from decksite.main import APP


class SmokeTest(unittest.TestCase):
    def setUp(self):
        # creates a test client
        self.app = APP.test_client()
        # propagate the exceptions to the test client
        self.app.testing = True

    def test_home_status_code(self):
        result = self.app.get('/')
        self.assertEqual(result.status_code, 200)

    def test_home_data(self):
        result = self.app.get('/')
        self.assertIn('<h1><string>Latest Decks</string></h1>', result.data.decode('utf-8'))

    @pytest.mark.slowtest
    def test_some_pages(self):
        result = self.app.get('/')
        self.assertEqual(result.status_code, 200)
        result = self.app.get('/archetypes/')
        self.assertEqual(result.status_code, 200)
        result = self.app.get('/people/')
        self.assertEqual(result.status_code, 200)
        result = self.app.get('/cards/')
        self.assertEqual(result.status_code, 200)
        result = self.app.get('/cards/Unsummon/')
        self.assertEqual(result.status_code, 200)
        result = self.app.get('/competitions/')
        self.assertEqual(result.status_code, 200)
        result = self.app.get('/competitions/')
        self.assertEqual(result.status_code, 200)
        result = self.app.get('/tournaments/')
        self.assertEqual(result.status_code, 200)
        result = self.app.get('/resources/')
        self.assertEqual(result.status_code, 200)
        result = self.app.get('/bugs/')
        self.assertEqual(result.status_code, 200)
        result = self.app.get('/signup/')
        self.assertEqual(result.status_code, 200)
        result = self.app.get('/report/')
        self.assertEqual(result.status_code, 200)
        result = self.app.get('/doesnotexist')
        self.assertEqual(result.status_code, 404)
