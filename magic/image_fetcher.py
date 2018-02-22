import hashlib
import os
import re

import magic.fetcher_internal as internal
from magic import oracle
from magic.fetcher_internal import FetchException, escape
from shared import configuration

if not os.path.exists(configuration.get('image_dir')):
    os.mkdir(configuration.get('image_dir'))

def basename(cards):
    from magic import card
    return '_'.join(re.sub('[^a-z-]', '-', card.canonicalize(c.name)) for c in cards)

def bluebones_image(cards) -> str:
    c = '|'.join(card.name for card in cards)
    return 'http://magic.bluebones.net/proxies/index2.php?c={c}'.format(c=escape(c))

def scryfall_image(card, version='') -> str:
    u = "https://api.scryfall.com/cards/named?exact={c}&format=image".format(c=escape(card.name))
    if version:
        u += '&version={v}'.format(v=escape(version))
    return u

def mci_image(printing) -> str:
    return "http://magiccards.info/scans/en/{code}/{number}.jpg".format(code=printing.set_code.lower(), number=printing.number)

def gatherer_image(printing) -> str:
    multiverse_id = printing.multiverseid
    if multiverse_id and int(multiverse_id) > 0:
        return 'https://image.deckbrew.com/mtg/multiverseid/'+ str(multiverse_id) + '.jpg'
    return None

def download_bluebones_image(cards, filepath) -> bool:
    print('Trying to get image for {cards}'.format(cards=', '.join(card.name for card in cards)))
    try:
        internal.store(bluebones_image(cards), filepath)
    except FetchException as e:
        print('Error: {e}'.format(e=e))
    return internal.acceptable_file(filepath)

def download_scryfall_image(cards, filepath, version='') -> bool:
    print('Trying to get scryfall image for {card}'.format(card=cards[0]))
    try:
        internal.store(scryfall_image(cards[0], version=version), filepath)
    except FetchException as e:
        print('Error: {e}'.format(e=e))
    return internal.acceptable_file(filepath)

def download_mci_image(cards, filepath) -> bool:
    printings = oracle.get_printings(cards[0])
    for p in printings:
        print("Trying to get MCI image for {imagename}".format(imagename=os.path.basename(filepath)))
        try:
            internal.store(mci_image(p), filepath)
            if internal.acceptable_file(filepath):
                return True
        except FetchException as e:
            print('Error: {e}'.format(e=e))
        print('Trying to get fallback image for {imagename}'.format(imagename=os.path.basename(filepath)))
        try:
            internal.store(gatherer_image(p), filepath)
            if internal.acceptable_file(filepath):
                return True
        except FetchException as e:
            print('Error: {e}'.format(e=e))
    return False

def determine_filepath(cards) -> str:
    imagename = basename(cards)
    # Hash the filename if it's otherwise going to be too large to use.
    if len(imagename) > 240:
        imagename = hashlib.md5(imagename.encode('utf-8')).hexdigest()
    filename = imagename + '.jpg'
    return '{dir}/{filename}'.format(dir=configuration.get('image_dir'), filename=filename)

def download_image(cards) -> str:
    filepath = determine_filepath(cards)
    if internal.acceptable_file(filepath):
        return filepath
    if download_bluebones_image(cards, filepath):
        return filepath
    if download_scryfall_image(cards, filepath):
        return filepath
    if download_mci_image(cards, filepath):
        return filepath
    return None
