from pathlib import Path

from magic import fetcher


def test_mtgo_guide_matches_resources() -> None:
    template = Path('decksite/templates/faqsbody.mustache').read_text(encoding='utf-8')
    guide_url = fetcher.resources()['Essentials']['Magic Online guide']

    assert f'[guide to Magic Online]({guide_url})' in template
