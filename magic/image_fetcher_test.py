from copy import copy
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from PIL import Image

from magic import image_fetcher, oracle
from magic.models import Card, Printing
from shared.fetch_tools import FetchException

GODZILLA_PRINTING_ID = '9a0639a0-c898-4a07-975c-a02bdd53175b'
WRONG_DIGITAL_PRINTING_ID = '1c48ddf5-c2da-4fbc-95f2-8a3f2f5737ba'
DEFAULT_PRINTING_ID = '88f3c600-66f1-4a5e-ba4f-61e9f7f7a1d9'


def test_resolve_printing_uses_exact_preferred_printing_id() -> None:
    c = Card({
        'name': 'Zilortha, Strength Incarnate',
        'preferred_printing': 'iko',
        'preferred_printing_system_id': GODZILLA_PRINTING_ID,
    })

    assert image_fetcher.resolve_printing(c).system_id == GODZILLA_PRINTING_ID  # type: ignore[union-attr]
    assert image_fetcher.basename([c]) == f'zilortha--strength-incarnate-iko-{GODZILLA_PRINTING_ID}'


def test_resolve_printing_uses_preferred_set(monkeypatch: pytest.MonkeyPatch) -> None:
    c = Card({'name': 'Sultai Ascendancy', 'preferred_printing': 'ktk'})
    printing = Printing({'system_id': DEFAULT_PRINTING_ID, 'set_code': 'ktk', 'image_status': 'highres_scan'})
    monkeypatch.setattr(oracle, 'get_printing', lambda _card, _set: printing)

    assert image_fetcher.resolve_printing(c) is printing


def test_resolve_printing_ignores_an_invalid_preferred_printing_id() -> None:
    c = Card({'name': 'Lightning Bolt', 'preferred_printing_system_id': '../../not-a-uuid'})

    assert image_fetcher.resolve_printing(c) is None
    assert image_fetcher.basename([c]) == 'lightning-bolt'


def test_resolve_printing_uses_default_and_skips_unusable_fallbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    c = Card({'id': 1, 'name': 'Lightning Bolt', 'default_printing_system_id': 'missing-id'})
    placeholder = Printing({'system_id': 'missing-id', 'image_status': 'missing'})
    usable = Printing({'system_id': DEFAULT_PRINTING_ID, 'image_status': 'lowres'})
    monkeypatch.setattr(oracle, 'get_printings', lambda _card: [placeholder, usable])

    assert image_fetcher.resolve_printing(c) is usable


def test_image_urls_put_cdn_before_id_api() -> None:
    c = Card({'name': 'Lightning Bolt', 'default_printing_system_id': DEFAULT_PRINTING_ID})

    assert image_fetcher.image_urls(c, version='art_crop') == [
        f'https://cards.scryfall.io/art_crop/front/8/8/{DEFAULT_PRINTING_ID}.jpg',
        f'https://api.scryfall.com/cards/{DEFAULT_PRINTING_ID}?format=image&version=art_crop',
    ]


def test_image_urls_without_a_printing_use_named_api() -> None:
    c = Card({'name': 'Fire // Ice'})

    assert image_fetcher.image_urls(c, version='art_crop') == [
        'https://api.scryfall.com/cards/named?exact=Fire+%2F%2F+Ice&format=image&version=art_crop',
    ]


def test_meld_back_uses_the_result_cards_printing() -> None:
    front = Card({
        'name': 'Gisela, the Broken Blade',
        'names': 'Gisela, the Broken Blade|Brisela, Voice of Nightmares',
        'meld_result_printing_system_id': DEFAULT_PRINTING_ID,
    })

    assert image_fetcher.image_urls(front, version='large', face='meld')[0] == (
        f'https://cards.scryfall.io/large/front/8/8/{DEFAULT_PRINTING_ID}.jpg'
    )


@pytest.mark.asyncio
async def test_download_tries_id_api_after_cdn_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    store = AsyncMock(side_effect=[FetchException('404'), None])
    monkeypatch.setattr(image_fetcher.fetch_tools, 'store_async', store)
    destination = str(tmp_path / 'card.jpg')
    urls = ['https://cards.scryfall.io/card.jpg', 'https://api.scryfall.com/cards/id?format=image']

    assert await image_fetcher.download_first_image(urls, destination)
    assert [call.args[0] for call in store.await_args_list] == urls


@pytest.mark.asyncio
async def test_double_faced_art_crop_only_downloads_the_front(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    card = Card({
        'name': 'Kytheon, Hero of Akros',
        'names': 'Kytheon, Hero of Akros|Gideon, Battle-Forged',
        'layout': 'transform',
        'default_printing_system_id': DEFAULT_PRINTING_ID,
    })
    download = AsyncMock(return_value=True)
    monkeypatch.setattr(image_fetcher, 'download_first_image', download)
    destination = str(tmp_path / 'kytheon.art_crop.jpg')

    await image_fetcher.download_scryfall_card_image(card, destination, version='art_crop')

    download.assert_awaited_once_with(image_fetcher.image_urls(card, version='art_crop'), destination)


def test_exact_printings_in_the_same_set_have_distinct_cache_keys() -> None:
    godzilla = Card({
        'name': 'Zilortha, Strength Incarnate',
        'preferred_printing': 'iko',
        'preferred_printing_system_id': GODZILLA_PRINTING_ID,
    })
    digital = copy(godzilla)
    digital['preferred_printing_system_id'] = WRONG_DIGITAL_PRINTING_ID

    assert image_fetcher.basename([godzilla]) != image_fetcher.basename([digital])


def test_default_printing_changes_the_cache_key() -> None:
    first = Card({'name': 'Lightning Bolt', 'default_printing_system_id': DEFAULT_PRINTING_ID})
    second = copy(first)
    second['default_printing_system_id'] = GODZILLA_PRINTING_ID

    assert image_fetcher.basename([first]) != image_fetcher.basename([second])


@pytest.mark.asyncio
async def test_download_small_art_crop_resizes_and_compresses(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    card = Card({'name': 'Reclaim', 'layout': 'normal'})
    source_path = tmp_path / 'source.jpg'
    output_path = tmp_path / 'small.jpg'
    Image.effect_noise((626, 457), 80).convert('RGB').save(source_path, quality=95)
    monkeypatch.setattr(image_fetcher, 'small_art_crop_filepath', lambda _card: str(output_path))
    monkeypatch.setattr(image_fetcher, 'download_scryfall_art_crop', AsyncMock(return_value=str(source_path)))

    result = await image_fetcher.download_small_art_crop(card)

    assert result == str(output_path)
    with Image.open(output_path) as image:
        assert image.format == 'JPEG'
        assert image.size == (320, 234)
    assert output_path.stat().st_size < source_path.stat().st_size


@pytest.mark.asyncio
async def test_small_art_crop_does_not_reuse_a_stale_double_faced_composite(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    card = Card({
        'name': 'Brutal Cathar',
        'names': 'Brutal Cathar|Moonrage Brute',
        'layout': 'transform',
        'default_printing_system_id': DEFAULT_PRINTING_ID,
    })
    output_path = tmp_path / 'small.jpg'
    download = AsyncMock(return_value=True)

    async def write_fresh_front(_urls: list[str], destination: str) -> bool:
        Image.effect_noise((626, 457), 80).convert('RGB').save(destination, quality=95)
        return True

    download.side_effect = write_fresh_front
    monkeypatch.setattr(image_fetcher, 'small_art_crop_filepath', lambda _card: str(output_path))
    monkeypatch.setattr(image_fetcher, 'download_first_image', download)
    stale_cache = AsyncMock(side_effect=AssertionError('must not use the old composite'))
    monkeypatch.setattr(image_fetcher, 'download_scryfall_art_crop', stale_cache)

    assert await image_fetcher.download_small_art_crop(card) == str(output_path)
    download.assert_awaited_once()
    assert download.await_args is not None
    assert download.await_args.args[0] == image_fetcher.image_urls(card, version='art_crop')
    stale_cache.assert_not_awaited()
    with Image.open(output_path) as image:
        assert image.size == (320, 234)


@pytest.mark.asyncio
async def test_download_image_async_uses_small_art_crop(monkeypatch: pytest.MonkeyPatch) -> None:
    card = Card({'name': 'Reclaim'})
    download = AsyncMock(return_value='/tmp/reclaim.art_crop_small.jpg')
    monkeypatch.setattr(image_fetcher, 'download_small_art_crop', download)

    assert await image_fetcher.download_image_async([card], version='art_crop_small') == '/tmp/reclaim.art_crop_small.jpg'
    download.assert_awaited_once_with(card)
