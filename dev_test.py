import dev


def test_find_files() -> None:
    assert dev.find_files('scraper', 'py') == ['decksite/scrapers/scraper_test.py']
    assert dev.find_files('', 'jsx') == ['shared_web/static/js/cardtable.jsx', 'shared_web/static/js/decktable.jsx', 'shared_web/static/js/persontable.jsx', 'shared_web/static/js/table.jsx']
