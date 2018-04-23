import pytest
import vcr

from decksite.main import APP
from decksite.scrapers import gatherling, tappedout


@pytest.mark.functional
@pytest.mark.tappedout
def test_tappedout():
    prev = APP.config['SERVER_NAME']
    APP.config['SERVER_NAME'] = '127:0.0.1:5000'
    with APP.app_context():
        tappedout.scrape()
    APP.config['SERVER_NAME'] = prev

@pytest.mark.functional
@pytest.mark.gatherling
@vcr.use_cassette(record_mode='new_episodes')
def test_gatherling():
    with APP.app_context():
        gatherling.scrape(5)

@pytest.mark.functional
@pytest.mark.tappedout
@vcr.use_cassette
def test_manual_tappedout():
    with APP.app_context():
        tappedout.scrape_url('https://tappedout.net/mtg-decks/60-island/') # Best deck
