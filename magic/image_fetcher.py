import hashlib
import re
import os

import magic.fetcher_internal as internal
from magic import oracle
from magic.fetcher_internal import FetchException, escape
from shared import configuration

os.mkdir(configuration.get('image_dir'))

def download_image(cards) -> str:
    # helper functions:
    def basename(cards):
        from magic import card
        return '_'.join(re.sub('[^a-z-]', '-', card.canonicalize(c.name)) for c in cards)
    def better_image(cards) -> str:
        c = '|'.join(card.name for card in cards)
        return 'http://magic.bluebones.net/proxies/?c={c}'.format(c=escape(c))
    def http_image(multiverse_id) -> str:
        return 'https://image.deckbrew.com/mtg/multiverseid/'+ str(multiverse_id)    +'.jpg'

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
        internal.store(better_image(cards), filepath)
    except FetchException as e:
        print('Error: {e}'.format(e=e))
    if internal.acceptable_file(filepath):
        return filepath

    printings = oracle.get_printings(cards[0])
    if len(printings) > 0:
        multiverse_id = printings[0].multiverseid
        if multiverse_id and int(multiverse_id) > 0:
            print('Trying to get fallback image for {imagename}'.format(imagename=imagename))
            try:
                internal.store(http_image(multiverse_id), filepath)
            except FetchException as e:
                print('Error: {e}'.format(e=e))
            if internal.acceptable_file(filepath):
                return filepath
    return None
