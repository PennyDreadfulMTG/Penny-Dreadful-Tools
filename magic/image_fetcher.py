import asyncio
import hashlib
import math
import os
import re
from typing import List, Optional

from PIL import Image

from magic import card, oracle
from magic.card import Printing
from magic.models import Card
from shared import configuration, fetch_tools
from shared.fetch_tools import FetchException, escape

if not os.path.exists(configuration.get_str('image_dir')):
    os.mkdir(configuration.get_str('image_dir'))

def basename(cards: List[Card]) -> str:
    return '_'.join(re.sub('[^a-z-]', '-', card.canonicalize(c.name)) + c.preferred_printing or '' for c in cards)

def bluebones_image(cards: List[Card]) -> str:
    c = '|'.join(c.name for c in cards)
    return 'http://magic.bluebones.net/proxies/index2.php?c={c}'.format(c=escape(c))

def scryfall_image(c: Card, version: str = '', face: str = None) -> str:
    if face == 'meld':
        name = c.names[1]
    elif ' // ' in c.name:
        name = c.name.replace(' // ', '/')
    else:
        name = c.name
    p = oracle.get_printing(c, c.preferred_printing)
    if p is not None:
        u = f'https://api.scryfall.com/cards/{p.set_code}/{p.number}?format=image'.format(c=escape(name))
    else:
        u = 'https://api.scryfall.com/cards/named?exact={c}&format=image'.format(c=escape(name))
    if version:
        u += '&version={v}'.format(v=escape(version))
    if face and face != 'meld':
        u += '&face={f}'.format(f=escape(face))
    return u

def mci_image(printing: Printing) -> str:
    return 'http://magiccards.info/scans/en/{code}/{number}.jpg'.format(code=printing.set_code.lower(), number=printing.number)

def gatherer_image(printing: Printing) -> Optional[str]:
    multiverse_id = printing.multiverseid
    if multiverse_id and int(multiverse_id) > 0:
        return 'https://image.deckbrew.com/mtg/multiverseid/'+ str(multiverse_id) + '.jpg'
    return None

def download_bluebones_image(cards: List[Card], filepath: str) -> bool:
    print('Trying to get image for {cards}'.format(cards=', '.join(c.name for c in cards)))
    try:
        fetch_tools.store(bluebones_image(cards), filepath)
    except FetchException as e:
        print('Error: {e}'.format(e=e))
    return fetch_tools.acceptable_file(filepath)

async def download_scryfall_image(cards: List[Card], filepath: str, version: str = '') -> bool:
    card_names = ', '.join(c.name for c  in cards)
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

async def download_scryfall_art_crop(c: Card) -> Optional[str]:
    file_path = re.sub('.jpg$', '.art_crop.jpg', determine_filepath([c]))
    if not fetch_tools.acceptable_file(file_path):
        await download_scryfall_card_image(c, file_path, version='art_crop')
    if fetch_tools.acceptable_file(file_path):
        return file_path
    return None

async def download_scryfall_png(c: Card) -> Optional[str]:
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
            if c.layout == 'transform':
                await fetch_tools.store_async(scryfall_image(c, version=version, face='back'), paths[1])
            if c.layout == 'meld':
                await fetch_tools.store_async(scryfall_image(c, version=version, face='meld'), paths[1])
            if (fetch_tools.acceptable_file(paths[0]) and fetch_tools.acceptable_file(paths[1])):
                save_composite_image(paths, filepath)
        else:
            await fetch_tools.store_async(scryfall_image(c, version=version), filepath)
    except FetchException as e:
        print('Error: {e}'.format(e=e))
    return fetch_tools.acceptable_file(filepath)

def determine_filepath(cards: List[Card], prefix: str = '') -> str:
    imagename = basename(cards)
    # Hash the filename if it's otherwise going to be too large to use.
    if len(imagename) > 240:
        imagename = hashlib.md5(imagename.encode('utf-8')).hexdigest()
    filename = imagename + '.jpg'
    directory = configuration.get('image_dir')
    return f'{directory}/{prefix}{filename}'


def download_image(cards: List[Card]) -> Optional[str]:
    event_loop = None
    try:
        event_loop = asyncio.get_event_loop()
    except RuntimeError:
        event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(event_loop)
    return event_loop.run_until_complete(download_image_async(cards))

async def download_image_async(cards: List[Card]) -> Optional[str]:
    filepath = determine_filepath(cards)
    if fetch_tools.acceptable_file(filepath):
        return filepath
    if await download_scryfall_image(cards, filepath, version='border_crop'):
        return filepath
    if download_bluebones_image(cards, filepath):
        return filepath
    return None

def save_composite_image(in_filepaths: List[str], out_filepath: str) -> None:
    images = list(map(Image.open, in_filepaths))
    for image in images:
        aspect_ratio = image.width / image.height
        image.thumbnail([aspect_ratio * 445, 445])
    widths, heights = zip(*(i.size for i in images))
    total_width = sum(widths)
    max_height = max(heights)
    new_image = Image.new('RGB', (total_width, max_height))
    x_offset = 0
    for image in images:
        new_image.paste(image, (x_offset, 0))
        x_offset += image.size[0]
    new_image.save(out_filepath)

async def generate_banner(names: List[str], background: str, v_crop: int = 33) -> str:
    cards = [oracle.load_card(name) for name in names]
    out_filepath = determine_filepath(cards, f'banner-{background}{v_crop}-')

    if fetch_tools.acceptable_file(out_filepath):
        return out_filepath

    canvas = Image.new('RGB', (1920, 210))
    c = oracle.load_card(background)
    file_path = await download_scryfall_art_crop(c)
    if file_path:
        with Image.open(file_path) as img:
            h = v_crop / 100 * 1315
            canvas.paste(img.resize((1920, 1315), Image.BICUBIC).crop((0, h, 1920, h + 210)))

    n = math.ceil(len(cards) / 2)
    x = 800
    for c in cards[:n]:
        ip = await download_scryfall_png(c)
        with Image.open(ip) as img:
            img = img.resize((160, 213), Image.LANCZOS)
            canvas.paste(img, (x, 30))
            x = x + img.width + 10
    x = 900
    for c in cards[n:]:
        ip = await download_scryfall_png(c)
        with Image.open(ip) as img:
            img = img.resize((160, 213), Image.LANCZOS)
            canvas.paste(img, (x, 60))
            x = x + img.width + 10

    canvas.save(out_filepath)
    return out_filepath
