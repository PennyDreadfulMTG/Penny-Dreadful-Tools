import asyncio
import hashlib
import math
import os
import re

from PIL import Image, ImageOps, UnidentifiedImageError

from magic import card, fetcher, layout, oracle
from magic.models import Card, Printing
from shared import configuration, fetch_tools
from shared.fetch_tools import FetchException, escape

if not os.path.exists(configuration.get_str('image_dir')):
    os.makedirs(configuration.get_str('image_dir'), exist_ok=True)


def basename(cards: list[Card]) -> str:
    return '_'.join(re.sub('[^a-z-]', '-', card.canonicalize(c.name)) + (c.get('preferred_printing', '') or '') for c in cards)


def bluebones_image(cards: list[Card]) -> str:
    c = '|'.join(c.name for c in cards)
    return f'http://magic.bluebones.net/proxies/index2.php?c={escape(c)}'


def scryfall_image(c: Card, version: str = '', face: str | None = None) -> str:
    if face == 'meld':
        name = c.names[1]
    elif ' // ' in c.name:
        name = c.name.replace(' // ', '/')
    else:
        name = c.name
    p = oracle.get_printing(c, c.get('preferred_printing'))
    if p is not None:
        u = f'https://api.scryfall.com/cards/{p.set_code}/{p.number}?format=image'
    else:
        u = f'https://api.scryfall.com/cards/named?exact={escape(name)}&format=image'
    if version:
        u += f'&version={escape(version)}'
    if face and face != 'meld':
        u += f'&face={escape(face)}'
    return u


def mci_image(printing: Printing) -> str:
    return f'http://magiccards.info/scans/en/{printing.set_code.lower()}/{printing.number}.jpg'


def gatherer_image(printing: Printing) -> str | None:
    multiverse_id = printing.multiverseid
    if multiverse_id and int(multiverse_id) > 0:
        return 'https://image.deckbrew.com/mtg/multiverseid/' + str(multiverse_id) + '.jpg'
    return None


def download_bluebones_image(cards: list[Card], filepath: str) -> bool:
    print('Trying to get image for {cards}'.format(cards=' • '.join(c.name for c in cards)))
    try:
        fetch_tools.store(bluebones_image(cards), filepath)
    except FetchException as e:
        print(f'Error: {e}')
    return fetch_tools.acceptable_file(filepath)


async def download_scryfall_image(cards: list[Card], filepath: str, version: str = '') -> bool:
    card_names = ', '.join(c.name for c in cards)
    print(f'Trying to get scryfall images for {card_names}')
    image_filepaths = []
    for c in cards:
        card_filepath = determine_filepath([c])
        if not fetch_tools.acceptable_file(card_filepath):
            await download_scryfall_card_image(c, card_filepath, version)
        if fetch_tools.acceptable_file(card_filepath):
            image_filepaths.append(card_filepath)
    if len(image_filepaths) > 1:
        save_composite_image(image_filepaths, filepath)
    return fetch_tools.acceptable_file(filepath)


async def download_art_crop(c: Card, hq_data: dict[str, tuple[str, int]]) -> str | None:
    if hq_data is None:
        hq_data = await fetcher.hq_artcrops()
    if c.name in hq_data:
        url = hq_data[c.name][0]
        file_path = re.sub('.jpg$', '.hq_art_crop.jpg', determine_filepath([c]))
        if not fetch_tools.acceptable_file(file_path):
            await fetch_tools.store_async(url, file_path)
        if fetch_tools.acceptable_file(file_path):
            return file_path
    return await download_scryfall_art_crop(c)


async def download_scryfall_art_crop(c: Card) -> str | None:
    file_path = re.sub('.jpg$', '.art_crop.jpg', determine_filepath([c]))
    if not fetch_tools.acceptable_file(file_path):
        await download_scryfall_card_image(c, file_path, version='art_crop')
    if fetch_tools.acceptable_file(file_path):
        return file_path
    return None


async def download_scryfall_png(c: Card) -> str | None:
    file_path = re.sub('.jpg$', '.png', determine_filepath([c]))
    if not fetch_tools.acceptable_file(file_path):
        await download_scryfall_card_image(c, file_path, version='png')
    if fetch_tools.acceptable_file(file_path):
        return file_path
    return None


async def download_scryfall_card_image(c: Card, filepath: str, version: str = '') -> bool:
    try:
        if c.is_double_sided():
            paths = [re.sub('.jpg$', '.a.jpg', filepath), re.sub('.jpg$', '.b.jpg', filepath)]
            await fetch_tools.store_async(scryfall_image(c, version=version), paths[0])
            if c.layout in layout.has_single_back():
                await fetch_tools.store_async(scryfall_image(c, version=version, face='back'), paths[1])
            if c.layout in layout.has_meld_back():
                await fetch_tools.store_async(scryfall_image(c, version=version, face='meld'), paths[1])
            if fetch_tools.acceptable_file(paths[0]) and fetch_tools.acceptable_file(paths[1]):
                save_composite_image(paths, filepath)
        else:
            await fetch_tools.store_async(scryfall_image(c, version=version), filepath)
    except FetchException as e:
        print(f'Error: {e}')
    return fetch_tools.acceptable_file(filepath)


def determine_filepath(cards: list[Card], prefix: str = '', ext: str = '.jpg') -> str:
    imagename = basename(cards)
    # Hash the filename if it's otherwise going to be too large to use.
    if len(imagename) > 240:
        imagename = hashlib.md5(imagename.encode('utf-8')).hexdigest()
    filename = imagename + ext
    directory = configuration.get('image_dir')
    return f'{directory}/{prefix}{filename}'


def download_image(cards: list[Card]) -> str | None:
    event_loop = None
    try:
        event_loop = asyncio.get_event_loop()
    except RuntimeError:
        event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(event_loop)
    return event_loop.run_until_complete(download_image_async(cards))


async def download_image_async(cards: list[Card]) -> str | None:
    filepath = determine_filepath(cards)
    if fetch_tools.acceptable_file(filepath):
        return filepath
    if await download_scryfall_image(cards, filepath, version='border_crop'):
        return filepath
    if download_bluebones_image(cards, filepath):
        return filepath
    return None


def save_composite_image(in_filepaths: list[str], out_filepath: str) -> None:
    try:
        images = list(map(Image.open, in_filepaths))
    except UnidentifiedImageError:
        for f in in_filepaths:
            os.remove(f)
        return None

    for image in images:
        aspect_ratio = image.width / image.height
        image.thumbnail([aspect_ratio * 445, 445])  # type: ignore
    widths, heights = zip(*(i.size for i in images))
    total_width = sum(widths)
    max_height = max(heights)
    new_image = Image.new('RGB', (total_width, max_height))
    x_offset = 0
    for image in images:
        new_image.paste(image, (x_offset, 0))
        x_offset += image.size[0]
    new_image.save(out_filepath)


async def generate_banner(names: list[str], background: str, v_crop: int | None = None) -> str:
    cards = [oracle.load_card(name) for name in names]
    hq_artcrops = fetcher.hq_artcrops()
    hq = False
    if background in hq_artcrops.keys():
        hq = True
        if v_crop is None:
            v_crop = hq_artcrops[background][1]

    if v_crop is None:
        v_crop = 33

    out_filepath = determine_filepath(cards, f'banner-{background}{"hq" if hq else ""}{v_crop}-', '.png')

    if fetch_tools.acceptable_file(out_filepath):
        return out_filepath

    canvas = Image.new('RGB', (1920, 210))
    c = oracle.load_card(background)
    file_path = await download_art_crop(c, hq_artcrops)
    if file_path:
        with Image.open(file_path) as img:
            h = int(v_crop / 100 * 1315)
            canvas.paste(img.resize((1920, 1315), Image.Resampling.BICUBIC).crop((0, h, 1920, h + 210)))

    n = math.ceil(len(cards) / 2)
    x = 800
    for c in cards[:n]:
        ip = await download_scryfall_png(c)
        with Image.open(ip) as img:
            img = img.resize((160, 213), Image.Resampling.LANCZOS)
            canvas.paste(img, (x, 30))
            x = x + img.width + 10
    x = 900
    for c in cards[n:]:
        ip = await download_scryfall_png(c)
        with Image.open(ip) as img:
            img = img.resize((160, 213), Image.Resampling.LANCZOS)
            canvas.paste(img, (x, 60))
            x = x + img.width + 10

    canvas.save(out_filepath)
    return out_filepath


async def generate_discord_banner(names: list[str], background: str) -> str:
    cards = [oracle.load_card(name) for name in names]
    hq_artcrops = fetcher.hq_artcrops()
    hq = False
    if background in hq_artcrops.keys():
        hq = True

    out_filepath = determine_filepath(cards, f'discord-banner-{background}{"hq" if hq else ""}-', '.png')

    if fetch_tools.acceptable_file(out_filepath):
        return out_filepath

    canvas = Image.new('RGB', (1920, 1080))
    c = oracle.load_card(background)
    file_path = await download_art_crop(c, hq_artcrops)
    if file_path:
        with Image.open(file_path) as img:
            img = ImageOps.fit(img, (1920, 1080))
            canvas.paste(img)

    n = math.ceil(len(cards) / 2)
    x = 200
    for c in cards[:n]:
        ip = await download_scryfall_png(c)
        with Image.open(ip) as img:
            img = img.resize((320, 426), Image.Resampling.LANCZOS)
            canvas.paste(img, (x, 500))
            x = x + img.width + 10
    x = 300
    for c in cards[n:]:
        ip = await download_scryfall_png(c)
        with Image.open(ip) as img:
            img = img.resize((320, 426), Image.Resampling.LANCZOS)
            canvas.paste(img, (x, 600))
            x = x + img.width + 10

    canvas.save(out_filepath)
    return out_filepath
