import re
import time

from bs4 import BeautifulSoup

from decksite.data import deck
from magic import decklist, fetcher, legality
from shared import dtutil
from shared.container import Container
from shared.pd_exception import InvalidDataException
from shared_web import logger


def scrape(limit: int = 255) -> None:
    page = 1
    while page <= limit:
        time.sleep(0.1)
        url = 'https://www.mtggoldfish.com/deck/custom/penny_dreadful?page={n}#online'.format(n=page)
        soup = BeautifulSoup(fetcher.internal.fetch(url, character_encoding='utf-8'), 'html.parser')
        raw_decks = soup.find_all('div', {'class': 'deck-tile'})
        if len(raw_decks) == 0:
            logger.warning('No decks found in {url} so stopping.'.format(url=url))
            break
        for raw_deck in raw_decks:
            d = Container({'source': 'MTG Goldfish'})
            a = raw_deck.select_one('h2 > span.deck-price-online > a')
            d.identifier = re.findall(r'/deck/(\d+)#online', a.get('href'))[0]
            d.url = 'https://www.mtggoldfish.com/deck/{identifier}#online'.format(identifier=d.identifier)
            d.name = a.contents[0].strip()
            d.mtggoldfish_username = raw_deck.select_one('div.deck-tile-author').contents[0].strip()
            remove_by = re.match(r'^(by )?(.*)$', d.mtggoldfish_username)
            if remove_by:
                d.mtggoldfish_username = remove_by.group(2)
            d.created_date = scrape_created_date(d)
            time.sleep(1)
            d.cards = scrape_decklist(d)
            try:
                vivified = decklist.vivify(d.cards)
            # MTGG doesn't do any validation of cards so some decks with fail here with card names like 'Stroke of Genuineness'.
            except InvalidDataException as e:
                logger.warning('Rejecting decklist of deck with identifier {identifier} because of {e}'.format(identifier=d.identifier, e=e))
                continue
            if len([f for f in legality.legal_formats(vivified) if 'Penny Dreadful' in f]) == 0:
                logger.warning('Rejecting deck with identifier {identifier} because it is not legal in any PD formats.'.format(identifier=d.identifier))
                continue
            if len(d.cards) == 0:
                logger.warning('Rejecting deck with identifier {identifier} because it has no cards.'.format(identifier=d.identifier))
                continue
            deck.add_deck(d)
        page += 1

def scrape_created_date(d: deck.Deck) -> int:
    soup = BeautifulSoup(fetcher.internal.fetch(d.url, character_encoding='utf-8'), 'html.parser')
    description = soup.select_one('div.deck-view-description').renderContents().decode('utf-8')
    date_s = re.findall(r'([A-Z][a-z][a-z] \d+, \d\d\d\d)', description)[0]
    return dtutil.parse_to_ts(date_s, '%b %d, %Y', dtutil.MTGGOLDFISH_TZ)

def scrape_decklist(d: deck.Deck) -> decklist.DecklistType:
    url = 'https://www.mtggoldfish.com/deck/download/{identifier}'.format(identifier=d.identifier)
    return decklist.parse(fetcher.internal.fetch(url))
