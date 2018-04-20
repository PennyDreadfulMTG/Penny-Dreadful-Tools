import unittest

from flask import appcontext_pushed, g, request

from decksite import view
from decksite.main import APP
from magic import rotation


class ViewTest(unittest.TestCase):
    def test_seasonized_url_for_app_endpoint(self):
        with APP.test_request_context('/decks/'):
            assert '/seasons/1/decks/' == view.seasonized_url(1)
            assert '/decks/' == view.seasonized_url(rotation.current_season_num())

    def test_seasonized_url_for_seasons_endpoint(self):
        with APP.test_request_context('/seasons/2/decks/'):
            assert '/seasons/1/decks/' == view.seasonized_url(1)
            assert '/decks/' == view.seasonized_url(rotation.current_season_num())

    def test_seasonized_url_when_not_seasonized(self):
        with APP.test_request_context('/tournaments/'):
            assert '/tournaments/' == view.seasonized_url(1)
            assert '/tournaments/' == view.seasonized_url(rotation.current_season_num())
