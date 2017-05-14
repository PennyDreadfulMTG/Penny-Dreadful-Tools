import hashlib
import re
import os

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
    return 'http://magic.bluebones.net/proxies/?c={c}'.format(c=escape(c))

def bluebones_alt_image(cards) -> str:
    c = '|'.join(card.name for card in cards)
    return 'http://magic.bluebones.net/proxies/index2.php?c={c}'.format(c=escape(c))

def scryfall_image(card) -> str:
    return "https://api.scryfall.com/cards/named?exact={c}&format=image".format(c=escape(card.name))

def mci_image(printing) -> str:
    return "http://magiccards.info/scans/en/{code}/{number}.jpg".format(code=printing.set_code.lower(), number=printing.number)

def gatherer_image(printing) -> str:
    multiverse_id = printing.multiverseid
    if multiverse_id and int(multiverse_id) > 0:
        return 'https://image.deckbrew.com/mtg/multiverseid/'+ str(multiverse_id) + '.jpg'

def download_image(cards) -> str:
    # helper functions:

    imagename = basename(cards)
    # Hash the filename if it's otherwise going to be too large to use.
    if len(imagename) > 240:
        imagename = hashlib.md5(imagename.encode('utf-8')).hexdigest()
    filename = imagename + '.jpg'
    filepath = '{dir}/{filename}'.format(dir=configuration.get('image_dir'), filename=filename)
    if internal.acceptable_file(filepath):
        return filepath
    print('Trying to get first choice image for {cards}'.format(cards=', '.join(card.name for card in cards)))
    try:
        internal.store(bluebones_image(cards), filepath)
    except FetchException as e:
        print('Error: {e}'.format(e=e))
    if internal.acceptable_file(filepath):
        return filepath

    print('Trying to get second choice image for {cards}'.format(cards=', '.join(card.name for card in cards)))
    try:
        internal.store(bluebones_alt_image(cards), filepath)
    except FetchException as e:
        print('Error: {e}'.format(e=e))
    if internal.acceptable_file(filepath):
        return filepath

    try:
        internal.store(scryfall_image(cards[0]), filepath)
    except FetchException as e:
        print('Error: {e}'.format(e=e))
    if internal.acceptable_file(filepath):
        return filepath

    printings = oracle.get_printings(cards[0])
    for p in printings:
        print("Trying to get MCI image for {imagename}".format(imagename=imagename))
        try:
            internal.store(mci_image(p), filepath)
            if internal.acceptable_file(filepath):
                return filepath
        except FetchException as e:
            print('Error: {e}'.format(e=e))
        print('Trying to get fallback image for {imagename}'.format(imagename=imagename))
        try:
            internal.store(gatherer_image(p), filepath)
            if internal.acceptable_file(filepath):
                return filepath
        except FetchException as e:
            print('Error: {e}'.format(e=e))
    return None
