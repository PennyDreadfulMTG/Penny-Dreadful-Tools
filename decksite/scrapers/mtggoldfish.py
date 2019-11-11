import re
import time

from bs4 import BeautifulSoup

from decksite.data import deck
from magic import decklist, legality
from shared import dtutil, fetch_tools
from shared.container import Container
from shared.pd_exception import InvalidDataException
from shared_web import logger


def scrape(limit: int = 1) -> None:
    page = 1
    while page <= limit:
        time.sleep(0.1)
        url = 'https://www.mtggoldfish.com/deck/custom/penny_dreadful?page={n}#online'.format(n=page)
        soup = BeautifulSoup(fetch_tools.fetch(url, character_encoding='utf-8'), 'html.parser')
        raw_decks = soup.find_all('div', {'class': 'deck-tile'})
        if len(raw_decks) == 0:
            logger.warning('No decks found in {url} so stopping.'.format(url=url))
            break
        for raw_deck in raw_decks:
            d = Container({'source': 'MTG Goldfish'})
            a = raw_deck.select_one('.title > span.deck-price-online > a')
            d.identifier = re.findall(r'/deck/(\d+)#online', a.get('href'))[0]
            d.url = 'https://www.mtggoldfish.com/deck/{identifier}#online'.format(identifier=d.identifier)
            d.name = a.contents[0].strip()
            d.mtggoldfish_username = without_by(raw_deck.select_one('div.deck-tile-author').contents[0].strip())
            try:
                d.created_date = scrape_created_date(d)
            except InvalidDataException as e:
                msg = f'Got {e} trying to find a created_date in {d}, {raw_deck}'
                logger.error(msg)
                raise InvalidDataException(msg)
            time.sleep(5)
            d.cards = scrape_decklist(d)
            err = vivify_or_error(d)
            if err:
                logger.warning(err)
                continue
            deck.add_deck(d)
        page += 1

def without_by(s: str) -> str:
    remove_by = re.match(r'^(by )?(.*)$', s)
    if remove_by:
        return remove_by.group(2)
    return s

def scrape_created_date(d: Container) -> int:
    soup = BeautifulSoup(fetch_tools.fetch(d.url, character_encoding='utf-8'), 'html.parser')
    return parse_created_date(soup)

def parse_created_date(soup: BeautifulSoup) -> int:
    description = str(soup.select_one('div.deck-view-description'))
    try:
        date_s = re.findall(r'([A-Z][a-z][a-z] \d+, \d\d\d\d)', description)[0]
    except IndexError as e:
        raise InvalidDataException(f'Unable to find a date in {description} because of {e}')
    return dtutil.parse_to_ts(date_s, '%b %d, %Y', dtutil.MTGGOLDFISH_TZ)

def scrape_decklist(d: Container) -> decklist.DecklistType:
    url = 'https://www.mtggoldfish.com/deck/download/{identifier}'.format(identifier=d.identifier)
    return decklist.parse(fetch_tools.fetch(url))

# Empty str return value = success, like Unix.
def vivify_or_error(d: Container) -> str:
    try:
        vivified = decklist.vivify(d.cards)
    # MTGG doesn't do any validation of cards so some decks with fail here with card names like 'Stroke of Genuineness'.
    except InvalidDataException as e:
        return 'Rejecting decklist of deck with identifier {identifier} because of {e}'.format(identifier=d.identifier, e=e)
    if len([f for f in legality.legal_formats(vivified) if 'Penny Dreadful' in f]) == 0:
        return 'Rejecting deck with identifier {identifier} because it is not legal in any PD formats.'.format(identifier=d.identifier)
    if len(d.cards) == 0:
        return 'Rejecting deck with identifier {identifier} because it has no cards.'.format(identifier=d.identifier)
    return ''

def scrape_one(url: str) -> Container:
    d = Container({'source': 'MTG Goldfish'})
    identifier_match = re.match('.*/deck/([^#]*)(?:#.*)?', url)
    if identifier_match is None:
        raise InvalidDataException('Cannot find identifier in URL. Is it a valid MTG Goldfish decklist URL?')
    d.identifier = identifier_match.group(1)
    d.url = url
    soup = BeautifulSoup(fetch_tools.fetch(d.url, character_encoding='utf-8'), 'html.parser')
    d.name = str(soup.select_one('h2.deck-view-title').contents[0]).strip()
    d.mtggoldfish_username = without_by(str(soup.select_one('span.deck-view-author').contents[0].strip()))
    d.created_date = parse_created_date(soup)
    try:
        d.cards = scrape_decklist(d)
    except InvalidDataException as e:
        raise InvalidDataException(f'Unable to scrape decklist for {d} because of {e}')
    error = vivify_or_error(d)
    if error:
        raise InvalidDataException(error)
    return deck.add_deck(d)
