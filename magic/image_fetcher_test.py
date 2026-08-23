from copy import copy

from magic import image_fetcher, oracle
from magic.models import Card

GODZILLA_PRINTING_ID = '9a0639a0-c898-4a07-975c-a02bdd53175b'
WRONG_DIGITAL_PRINTING_ID = '1c48ddf5-c2da-4fbc-95f2-8a3f2f5737ba'


def test_scryfall_image_uses_default_printing_within_preferred_set() -> None:
    c = copy(oracle.load_card('Sultai Ascendancy'))
    c['preferred_printing'] = 'ktk'

    assert image_fetcher.basename([c]) == 'sultai-ascendancy-ktk'
    assert image_fetcher.scryfall_image(c, version='border_crop') == (
        'https://api.scryfall.com/cards/named?exact=sultai+ascendancy&set=ktk&format=image&version=border_crop'
    )

def test_scryfall_image_uses_exact_preferred_printing_id() -> None:
    c = Card({
        'name': 'Zilortha, Strength Incarnate',
        'preferred_printing': 'iko',
        'preferred_printing_system_id': GODZILLA_PRINTING_ID,
    })

    assert image_fetcher.scryfall_image(c, version='border_crop') == (
        f'https://api.scryfall.com/cards/{GODZILLA_PRINTING_ID}?format=image&version=border_crop'
    )
    assert image_fetcher.basename([c]) == f'zilortha--strength-incarnate-iko-{GODZILLA_PRINTING_ID}'

def test_exact_printings_in_the_same_set_have_distinct_cache_keys() -> None:
    godzilla = Card({
        'name': 'Zilortha, Strength Incarnate',
        'preferred_printing': 'iko',
        'preferred_printing_system_id': GODZILLA_PRINTING_ID,
    })
    digital = Card({
        'name': 'Zilortha, Strength Incarnate',
        'preferred_printing': 'iko',
        'preferred_printing_system_id': WRONG_DIGITAL_PRINTING_ID,
    })

    assert image_fetcher.basename([godzilla]) != image_fetcher.basename([digital])

def test_canonical_card_uses_default_printing() -> None:
    c = Card({'name': 'Zilortha, Strength Incarnate'})

    assert image_fetcher.basename([c]) == 'zilortha--strength-incarnate'
    assert image_fetcher.scryfall_image(c, version='border_crop') == (
        'https://api.scryfall.com/cards/named?exact=zilortha%2c+strength+incarnate&format=image&version=border_crop'
    )
