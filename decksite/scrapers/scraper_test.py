import pytest
import vcr

from decksite import APP
from decksite.scrapers import mtggoldfish
from shared import configuration

TEST_VCR = vcr.VCR(
    record_mode=configuration.get('test_vcr_record_mode'),
    path_transformer=vcr.VCR.ensure_suffix('.yaml'),
)

@pytest.mark.functional
@pytest.mark.goldfish
@pytest.mark.external
@TEST_VCR.use_cassette
def test_goldfish() -> None:
    with APP.app_context():
        mtggoldfish.scrape(1)
