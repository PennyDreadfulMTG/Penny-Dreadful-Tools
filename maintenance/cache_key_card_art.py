import time

from decksite.data import playability
from decksite.prepare import is_uninteresting
from magic import image_fetcher, oracle, seasons
from magic.models import Card
from shared import logger

DAILY = True

KEY_CARDS_PER_TILE = 5
# /cards/named is limited to 2 requests a second and nothing is waiting on us, so leave plenty of headroom.
# See https://scryfall.com/docs/api/rate-limits
SECONDS_BETWEEN_DOWNLOADS = 1.0

def run() -> None:
    """Download the art crops /metagame shows on its archetype tiles.

    The tiles used to hotlink api.scryfall.com from the visitor's browser, which meant one pageview fired
    ~100 requests at an endpoint that allows 2 a second and about half came back 429. They come from
    /image/ now, so all that's left is making sure a cold cache doesn't leave the first visitor after a
    deploy waiting on Scryfall. Do that out of band instead.
    """
    cards = key_cards()
    logger.info(f'Checking art crops for {len(cards)} key cards')
    downloaded, failed = 0, []
    for card in cards:
        if image_fetcher.art_crop_is_cached(card):
            continue
        if image_fetcher.download_image([card], version='art_crop') is None:
            failed.append(card.name)
        else:
            downloaded += 1
        time.sleep(SECONDS_BETWEEN_DOWNLOADS)
    logger.info(f'Downloaded {downloaded} art crops, {len(failed)} failed')
    if failed:
        logger.warning(f'Failed to get art crops for: {", ".join(failed)}')

def key_cards() -> list[Card]:
    """Every card that can appear on a /metagame tile, for any season or all-time.

    That's ~8k cards, so the first run takes a couple of hours. After that it's a no-op apart from whatever
    became a key card since yesterday. Warming old seasons too matters because a cold season page fires
    100+ fetches at Scryfall from our server at once and most of them come back 429."""
    cards_by_name = oracle.cards_by_name()
    found = {}
    for season_id in [0, *range(1, seasons.current_season_num() + 1)]:
        for names in playability.key_cards_long(season_id).values():
            cards = [card for name in names if (card := cards_by_name.get(name)) is not None]
            for card in [c for c in cards if not is_uninteresting(c)][0:KEY_CARDS_PER_TILE]:
                found[card.name] = card
    return [found[name] for name in sorted(found)]
