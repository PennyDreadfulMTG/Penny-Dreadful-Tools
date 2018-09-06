import hashlib
import os
import re
from typing import List, Optional

from PIL import Image

import shared.fetcher_internal as internal
from magic import oracle
from magic.card import Printing
from magic.models.card import Card
from shared import configuration
from shared.fetcher_internal import FetchException, escape

if not os.path.exists(configuration.get_str('image_dir')):
    os.mkdir(configuration.get_str('image_dir'))

def basename(cards: List[Card]) -> str:
    from magic import card
    return '_'.join(re.sub('[^a-z-]', '-', card.canonicalize(c.name)) for c in cards)

def bluebones_image(cards: List[Card]) -> str:
    c = '|'.join(card.name for card in cards)
    return 'http://magic.bluebones.net/proxies/index2.php?c={c}'.format(c=escape(c))

def scryfall_image(card: Card, version: str = '', face: str = None) -> str:
    if face == 'meld':
        name = card.names[1]
    elif ' // ' in card.name:
        name = card.name.replace(' // ', '/')
    else:
        name = card.name
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
    print('Trying to get image for {cards}'.format(cards=', '.join(card.name for card in cards)))
    try:
        internal.store(bluebones_image(cards), filepath)
    except FetchException as e:
        print('Error: {e}'.format(e=e))
    return internal.acceptable_file(filepath)

# BAKERT maybe detect 4xx responses here?
def download_scryfall_image(cards: List[Card], filepath: str, version: str = '') -> bool:
    card_names = ', '.join(card.name for card in cards)
    print(f'Trying to get scryfall images for {card_names}')
    image_filepaths = []
    for card in cards:
        card_filepath = determine_filepath([card], version)
        if not internal.acceptable_file(card_filepath):
            download_scryfall_card_image(card, card_filepath, version)
        if internal.acceptable_file(card_filepath):
            image_filepaths.append(card_filepath)
    if len(image_filepaths) > 1:
        save_composite_image(image_filepaths, filepath)
    return internal.acceptable_file(filepath)

def download_scryfall_card_image(card: Card, filepath: str, version: str = '') -> bool:
    try:
        if card.is_double_sided():
            paths = [re.sub('.jpg$', '.a.jpg', filepath), re.sub('.jpg$', '.b.jpg', filepath)]
            internal.store(scryfall_image(card, version=version), paths[0])
            if card.layout == 'double-faced':
                internal.store(scryfall_image(card, version=version, face='back'), paths[1])
            if card.layout == 'meld':
                internal.store(scryfall_image(card, version=version, face='meld'), paths[1])
            if (internal.acceptable_file(paths[0]) and internal.acceptable_file(paths[1])):
                save_composite_image(paths, filepath)
        else:
            internal.store(scryfall_image(card, version=version), filepath)
    except FetchException as e:
        print('Error: {e}'.format(e=e))
    return internal.acceptable_file(filepath)

def download_mci_image(cards: List[Card], filepath: str) -> bool:
    printings = oracle.get_printings(cards[0])
    for p in printings:
        print('Trying to get MCI image for {imagename}'.format(imagename=os.path.basename(filepath)))
        try:
            internal.store(mci_image(p), filepath)
            if internal.acceptable_file(filepath):
                return True
        except FetchException as e:
            print('Error: {e}'.format(e=e))
        print('Trying to get fallback image for {imagename}'.format(imagename=os.path.basename(filepath)))
        try:
            img = gatherer_image(p)
            if img:
                internal.store(img, filepath)
            if internal.acceptable_file(filepath):
                return True
        except FetchException as e:
            print('Error: {e}'.format(e=e))
    return False

def determine_filepath(cards: List[Card], version: str = '') -> str:
    imagename = basename(cards)
    # Hash the filename if it's otherwise going to be too large to use.
    if len(imagename) > 240:
        imagename = hashlib.md5(imagename.encode('utf-8')).hexdigest()
    if version == '':
        version = 'default'
    filename = f'{imagename}.{version}.jpg'
    return '{dir}/{filename}'.format(dir=configuration.get('image_dir'), filename=filename)

def download_image(cards: List[Card]) -> Optional[str]:
    filepath = determine_filepath(cards)
    if internal.acceptable_file(filepath):
        return filepath
    if download_scryfall_image(cards, filepath, version='border_crop'):
        return filepath
    if download_bluebones_image(cards, filepath):
        return filepath
    if download_mci_image(cards, filepath):
        return filepath
    return None

def save_composite_image(in_filepaths: List[str], out_filepath: str) -> None:
    images = list(map(Image.open, in_filepaths))
    for image in images:
        image.thumbnail([312, 445])
    widths, heights = zip(*(i.size for i in images))
    total_width = sum(widths)
    max_height = max(heights)
    new_image = Image.new('RGB', (total_width, max_height))
    x_offset = 0
    for image in images:
        new_image.paste(image, (x_offset, 0))
        x_offset += image.size[0]
    new_image.save(out_filepath)
