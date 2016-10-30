from decksite.main import APP
from decksite.scrapers import tappedout, gatherling

def test_tappedout():
    APP.config["SERVER_NAME"] = "127:0.0.1:5000"
    with APP.app_context():
        tappedout.scrape()

def test_gatherling():
    APP.config["SERVER_NAME"] = "127:0.0.1:5000"
    with APP.app_context():
        gatherling.scrape()
