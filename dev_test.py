import dev


def test_find_files() -> None:
    assert dev.find_files('scraper', 'py') == ['decksite/scrapers/scraper_test.py']
