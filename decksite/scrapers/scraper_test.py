import pytest

from decksite.main import APP
from decksite.scrapers import gatherling, tappedout


@pytest.mark.slowtest
@pytest.mark.tappedout
def test_tappedout():
    prev = APP.config["SERVER_NAME"]
    APP.config["SERVER_NAME"] = "127:0.0.1:5000"
    with APP.app_context():
        tappedout.scrape()
    APP.config["SERVER_NAME"] = prev

@pytest.mark.slowtest
@pytest.mark.gatherling
def test_gatherling():
    with APP.app_context():
        gatherling.scrape(5)

@pytest.mark.tappedout
def test_manual_tappedout():
    with APP.app_context():
        tappedout.scrape_url('https://tappedout.net/mtg-decks/60-island/') # Best deck
