import pytest
import vcr

from decksite.main import APP
from decksite.scrapers import gatherling, mtggoldfish, tappedout
from shared import configuration

TEST_VCR = vcr.VCR(
    record_mode=configuration.get('test_vcr_record_mode'),
    path_transformer=vcr.VCR.ensure_suffix('.yaml'),
    )

@pytest.mark.functional
@pytest.mark.tappedout
@pytest.mark.external
@TEST_VCR.use_cassette
def test_tappedout() -> None:
    prev = APP.config['SERVER_NAME']
    APP.config['SERVER_NAME'] = '127:0.0.1:5000'
    with APP.app_context():
        tappedout.scrape()
    APP.config['SERVER_NAME'] = prev

@pytest.mark.functional
@pytest.mark.gatherling
@pytest.mark.external
@TEST_VCR.use_cassette
def test_gatherling() -> None:
    with APP.app_context():
        gatherling.scrape(5)

@pytest.mark.functional
@pytest.mark.tappedout
@pytest.mark.external
@TEST_VCR.use_cassette
def test_manual_tappedout() -> None:
    with APP.app_context():
        tappedout.scrape_url('https://tappedout.net/mtg-decks/60-island/') # Best deck

@pytest.mark.functional
@pytest.mark.goldfish
@pytest.mark.external
@TEST_VCR.use_cassette
def test_goldfish() -> None:
    with APP.app_context():
        mtggoldfish.scrape(1)
