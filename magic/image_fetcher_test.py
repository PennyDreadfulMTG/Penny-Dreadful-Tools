from copy import copy

from magic import image_fetcher, oracle


def test_scryfall_image_uses_default_printing_within_preferred_set() -> None:
    c = copy(oracle.load_card('Sultai Ascendancy'))
    c['preferred_printing'] = 'ktk'

    assert image_fetcher.basename([c]) == 'sultai-ascendancy-ktk'
    assert image_fetcher.scryfall_image(c, version='border_crop') == (
        'https://api.scryfall.com/cards/named?exact=sultai+ascendancy&set=ktk&format=image&version=border_crop'
    )
