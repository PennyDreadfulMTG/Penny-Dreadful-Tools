import asyncio
from magic import multiverse


def scrape() -> None:
    event_loop = None
    try:
        event_loop = asyncio.get_event_loop()
    except RuntimeError:
        event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(event_loop)

    event_loop.run_until_complete(multiverse.update_bugged_cards_async())
    multiverse.rebuild_cache()
