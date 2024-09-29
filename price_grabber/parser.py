import csv
import html
import re
import traceback
from io import StringIO

from magic import card, multiverse
from magic.database import db
from shared import logger
from shared.pd_exception import DatabaseException, InvalidDataException

PriceListType = list[tuple[str, str, str]]

CARDS: dict[str, str] = {}


def parse_cardhoarder_prices(s: str) -> PriceListType:
    details = []
    reader = csv.reader(StringIO(s), delimiter='\t', quotechar='"', doublequote=True)
    next(reader)  # Skip date line
    next(reader)  # Skip header line
    for line in reader:
        if len(line) != 7:
            raise InvalidDataException(f'Bad line (cardhoarder): {line}')
        _mtgo_id, mtgo_set, _mtgjson_set, set_number, name, p, quantity = line
        name = html.unescape(name.strip())
        name = repair_name(name)
        if int(quantity) > 0 and not mtgo_set.startswith('CH-') and mtgo_set != 'VAN' and mtgo_set != 'EVENT' and not re.search(r'(Booster|Commander Deck|Commander:|Theme Deck|Draft Pack|Duel Decks|Reward Pack|Intro Pack|Tournament Pack|Premium Deck Series:|From the Vault)', name):
            details.append((name, p, mtgo_set))
    return [(name_lookup(name), html.unescape(p.strip()), mtgo_set) for name, p, mtgo_set in details if name_lookup(name) is not None]

def repair_name(name: str) -> str:
    if name == 'Tura Kenner':
        name = 'Tura Kennerüd, Skyknight'
    elif name == 'Lurrus of the Dream Den':
        name = 'Lurrus of the Dream-Den'
    elif name == 'Kongming, Sleeping Dragon':
        name = 'Kongming, "Sleeping Dragon"'
    elif name == 'Pang Tong, Young Phoenix':
        name = 'Pang Tong, "Young Phoenix"'
    elif name.endswith(' - Sketch'):
        name = name[:-9]
    elif name == 'Sticker Goblin':
        name = '_____ Goblin'
    elif name == 'Ratonhnhaké:ton':
        name = 'Ratonhnhaké꞉ton'  # The colon here is a special char.
    elif name == 'Name Sticker Goblin':
        name = '"Name Sticker" Goblin'
    name = name.replace(' && ', ' // ')
    return name

def is_exceptional_name(name: str) -> bool:
    return name.startswith('APAC ') or 'Alternate art' in name or name.startswith('Avatar - ') or name.startswith('Euro ') or 'Reward Pack' in name

def name_lookup(name: str) -> str:
    try:
        if not CARDS:
            rs = db().select(multiverse.base_query())
            for row in rs:
                CARDS[card.canonicalize(row['name'])] = row['name']
                if row['flavor_names']:
                    for fn in row['flavor_names'].split('|'):
                        CARDS[card.canonicalize(fn)] = row['name']
    except DatabaseException:
        tb = traceback.format_exc()
        print(tb)
        if not CARDS:
            CARDS[''] = ''  # Filler, so that we don't try to do this every lookup.

    canonical = card.canonicalize(name)
    if canonical not in CARDS:
        if CARDS.get('', None) is None:
            logger.error(f'WARNING: Bogus name {name} ({canonical}) found.')
        return name
    return CARDS[canonical]
