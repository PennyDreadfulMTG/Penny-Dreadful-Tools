import asyncio
import hashlib
import math
import os
import re
import tempfile
from urllib import parse

from PIL import Image, ImageOps, UnidentifiedImageError

from magic import card, fetcher, layout, oracle
from magic.models import Card, Printing
from shared import configuration, fetch_tools
from shared.fetch_tools import FetchException, escape

UNUSABLE_IMAGE_STATUSES = {'placeholder', 'missing'}
SCRYFALL_ID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
SMALL_ART_CROP_WIDTH = 320
SMALL_ART_CROP_QUALITY = 80

if not os.path.exists(configuration.get_str('image_dir')):
    os.makedirs(configuration.get_str('image_dir'), exist_ok=True)

def basename(cards: list[Card]) -> str:
    return '_'.join(card_basename(c) for c in cards)

def card_basename(c: Card) -> str:
    result = re.sub('[^a-z-]', '-', card.canonicalize(c.name))
    preferred_set = c.get('preferred_printing')
    preferred_id = c.get('preferred_printing_system_id')
    if preferred_set:
        result += f'-{cache_key_component(preferred_set)}'
    if preferred_id and SCRYFALL_ID.fullmatch(preferred_id):
        result += f'-{preferred_id.lower()}'
    elif not preferred_set and (default_id := c.get('default_printing_system_id')):
        result += f'-{cache_key_component(default_id)}'
    return result

def cache_key_component(value: object) -> str:
    return re.sub('[^a-z0-9-]', '-', str(value).lower())

def bluebones_image(cards: list[Card]) -> str:
    c = '|'.join(c.name for c in cards)
    return f'http://magic.bluebones.net/proxies/index2.php?c={escape(c)}'

def resolve_printing(c: Card) -> Printing | None:
    """Resolve a card to a usable printing without consulting Scryfall's API."""
    preferred_printing_system_id = c.get('preferred_printing_system_id')
    if preferred_printing_system_id and SCRYFALL_ID.fullmatch(preferred_printing_system_id):
        return Printing({'system_id': preferred_printing_system_id, 'image_status': None})

    preferred_set = c.get('preferred_printing')
    if preferred_set:
        preferred = oracle.get_printing(c, preferred_set)
        if preferred is not None:
            return preferred

    default_printing_system_id = c.get('default_printing_system_id')
    if c.get('id') is None:
        if default_printing_system_id:
            return Printing({'system_id': default_printing_system_id, 'image_status': None})
        return None

    printings = oracle.get_printings(c)
    if default_printing_system_id:
        default = next((p for p in printings if p.system_id == default_printing_system_id), None)
        if default is not None and default.get('image_status') not in UNUSABLE_IMAGE_STATUSES:
            return default
    return next((p for p in printings if p.get('image_status') not in UNUSABLE_IMAGE_STATUSES), None)

def cdn_image_url(system_id: str, version: str, face: str = 'front') -> str:
    cdn_version = version or 'large'
    extension = 'png' if cdn_version == 'png' else 'jpg'
    return f'https://cards.scryfall.io/{cdn_version}/{face}/{system_id[0]}/{system_id[1]}/{system_id}.{extension}'

def api_image_url(system_id: str, version: str = '', face: str | None = None) -> str:
    query = {'format': 'image'}
    if version:
        query['version'] = version
    if face:
        query['face'] = face
    return f'https://api.scryfall.com/cards/{parse.quote(system_id, safe="")}?{parse.urlencode(query)}'

def named_api_image_url(name: str, version: str = '') -> str:
    query = {'exact': name, 'format': 'image'}
    if version:
        query['version'] = version
    return f'https://api.scryfall.com/cards/named?{parse.urlencode(query)}'

def image_urls(c: Card, version: str = '', face: str | None = None) -> list[str]:
    if face == 'meld':
        meld_result_id = c.get('meld_result_printing_system_id')
        printing = Printing({'system_id': meld_result_id, 'image_status': None}) if meld_result_id else None
        image_name = c.names[1]
    else:
        printing = resolve_printing(c)
        image_name = c.name
    if printing is None:
        return [named_api_image_url(image_name, version)]

    image_face = face if face and face != 'meld' else 'front'
    api_face = face if face and face != 'meld' else None
    return [
        cdn_image_url(printing.system_id, version, image_face),
        api_image_url(printing.system_id, version, api_face),
    ]

def scryfall_image(c: Card, version: str = '', face: str | None = None) -> str:
    """Return the API fallback URL retained for callers that need one URL."""
    return image_urls(c, version, face)[-1]

def mci_image(printing: Printing) -> str:
    return f'http://magiccards.info/scans/en/{printing.set_code.lower()}/{printing.number}.jpg'

def gatherer_image(printing: Printing) -> str | None:
    multiverse_id = printing.multiverseid
    if multiverse_id and int(multiverse_id) > 0:
        return 'https://image.deckbrew.com/mtg/multiverseid/' + str(multiverse_id) + '.jpg'
    return None

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

async def download_art_crop(c: Card, hq_data: dict[str, tuple[str, int]] | None) -> str | None:
    if hq_data is None:
        hq_data = fetcher.hq_artcrops()
    if c.name in hq_data:
        url = hq_data[c.name][0]
        file_path = re.sub('.jpg$', '.hq_art_crop.jpg', determine_filepath([c]))
        if not fetch_tools.acceptable_file(file_path):
            await fetch_tools.store_async(url, file_path)
        if fetch_tools.acceptable_file(file_path):
            return file_path
    return await download_scryfall_art_crop(c)

def art_crop_filepath(c: Card) -> str:
    return re.sub('.jpg$', '.art_crop.jpg', determine_filepath([c]))

def small_art_crop_filepath(c: Card) -> str:
    return re.sub('.jpg$', '.art_crop_small.jpg', determine_filepath([c]))

def art_crop_is_cached(c: Card) -> bool:
    return fetch_tools.acceptable_file(art_crop_filepath(c))

async def download_scryfall_art_crop(c: Card) -> str | None:
    file_path = art_crop_filepath(c)
    if not fetch_tools.acceptable_file(file_path):
        await download_scryfall_card_image(c, file_path, version='art_crop')
    if fetch_tools.acceptable_file(file_path):
        return file_path
    return None

async def download_small_art_crop(c: Card) -> str | None:
    """Create a lightweight art crop for image-heavy thumbnail grids."""
    file_path = small_art_crop_filepath(c)
    if fetch_tools.acceptable_file(file_path):
        return file_path

    temporary_path = ''
    temporary_output_path = ''
    source_path: str | None = None
    try:
        # Older releases cached double-faced art crops as a side-by-side composite. Do not derive a
        # thumbnail from that stale file: fetch the front-face crop into a temporary source instead.
        if c.is_double_sided():
            directory = os.path.dirname(os.path.abspath(file_path))
            with tempfile.NamedTemporaryFile(dir=directory, suffix='.jpg', delete=False) as temporary:
                temporary_path = temporary.name
            if not await download_first_image(image_urls(c, version='art_crop'), temporary_path):
                return None
            source_path = temporary_path
        else:
            source_path = await download_scryfall_art_crop(c)
        if source_path is None:
            return None
        with Image.open(source_path) as source:
            image = source.convert('RGB')
            if image.width > SMALL_ART_CROP_WIDTH:
                height = round(image.height * SMALL_ART_CROP_WIDTH / image.width)
                image = image.resize((SMALL_ART_CROP_WIDTH, height), Image.Resampling.LANCZOS)
            directory = os.path.dirname(os.path.abspath(file_path))
            with tempfile.NamedTemporaryFile(dir=directory, suffix='.jpg', delete=False) as temporary_output:
                temporary_output_path = temporary_output.name
            image.save(temporary_output_path, quality=SMALL_ART_CROP_QUALITY, optimize=True, progressive=True)
            os.replace(temporary_output_path, file_path)
            temporary_output_path = ''
    except (OSError, UnidentifiedImageError):
        return None
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.remove(temporary_path)
        if temporary_output_path and os.path.exists(temporary_output_path):
            os.remove(temporary_output_path)
    return file_path if fetch_tools.acceptable_file(file_path) else None

async def download_scryfall_png(c: Card) -> str | None:
    file_path = re.sub('.jpg$', '.png', determine_filepath([c]))
    if not fetch_tools.acceptable_file(file_path):
        await download_scryfall_card_image(c, file_path, version='png')
    if fetch_tools.acceptable_file(file_path):
        return file_path
    return None

async def download_scryfall_card_image(c: Card, filepath: str, version: str = '') -> bool:
    if c.is_double_sided() and version != 'art_crop':
        split = os.path.splitext(filepath)

        if f'.{version}' in filepath:
            paths = [f'{split[0]}.a{split[1]}', f'{split[0]}.b{split[1]}']
        else:
            paths = [f'{split[0]}.{version}.a{split[1]}', f'{split[0]}.{version}.b{split[1]}']

        front_ok = await download_first_image(image_urls(c, version=version), paths[0])
        back_ok = False
        if c.layout in layout.has_single_back():
            back_ok = await download_first_image(image_urls(c, version=version, face='back'), paths[1])
        if c.layout in layout.has_meld_back():
            back_ok = await download_first_image(image_urls(c, version=version, face='meld'), paths[1])
        if front_ok and back_ok:
            save_composite_image(paths, filepath)
    else:
        await download_first_image(image_urls(c, version=version), filepath)
    return fetch_tools.acceptable_file(filepath)

async def download_first_image(urls: list[str], filepath: str) -> bool:
    for url in urls:
        try:
            await fetch_tools.store_async(url, filepath)
            return True
        except FetchException as e:
            print(f'Error fetching {url}: {e}')
    return False

def determine_filepath(cards: list[Card], prefix: str = '', ext: str = '.jpg') -> str:
    imagename = basename(cards)
    # Hash the filename if it's otherwise going to be too large to use.
    if len(imagename) > 240:
        imagename = hashlib.md5(imagename.encode('utf-8')).hexdigest()
    filename = imagename + ext
    directory = configuration.get('image_dir')
    return f'{directory}/{prefix}{filename}'


def download_image(cards: list[Card], version: str = '') -> str | None:
    event_loop = None
    try:
        event_loop = asyncio.get_event_loop()
    except RuntimeError:
        event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(event_loop)
    return event_loop.run_until_complete(download_image_async(cards, version))

async def download_image_async(cards: list[Card], version: str = '') -> str | None:
    if version in ('art_crop', 'art_crop_small'):
        if len(cards) != 1:
            return None  # There's no such thing as a composite art crop.
        if version == 'art_crop_small':
            return await download_small_art_crop(cards[0])
        return await download_scryfall_art_crop(cards[0])
    filepath = determine_filepath(cards)
    if fetch_tools.acceptable_file(filepath):
        return filepath
    if await download_scryfall_image(cards, filepath, version='border_crop'):
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
    y = 30
    card_size = (160, 213)
    for c in cards[:n]:
        x = await paste_card(canvas, c, x, y, card_size)

    x = 900
    y = 60
    for c in cards[n:]:
        x = await paste_card(canvas, c, x, y, card_size)

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
            newimg = ImageOps.fit(img, (1920, 1080))
            canvas.paste(newimg)

    n = math.ceil(len(cards) / 2)
    card_size = (320, 426)
    x = 200
    y = 500
    for c in cards[:n]:
        x = await paste_card(canvas, c, x, y, card_size)

    x = 300
    y = 600
    for c in cards[n:]:
        x = await paste_card(canvas, c, x, y, card_size)

    canvas.save(out_filepath)
    return out_filepath

async def paste_card(canvas: Image.Image, c: Card, x: int, y: int, card_size: tuple[int, int]) -> int:
    filepath = await download_scryfall_png(c)
    if filepath is None:
        return x

    with Image.open(filepath) as img:
        newimg = img.resize(card_size, Image.Resampling.LANCZOS)
        canvas.paste(newimg, (x, y))
        x = x + newimg.width + 10
    return x
