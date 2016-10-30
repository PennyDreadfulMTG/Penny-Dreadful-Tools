from decksite.scrapers import tappedout, gatherling

def test_tappedout():
    tappedout.scrape()

def test_gatherling():
    gatherling.scrape()
