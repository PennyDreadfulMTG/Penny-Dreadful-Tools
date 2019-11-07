from magic import multiverse


def scrape() -> None:
    multiverse.update_bugged_cards()
    multiverse.rebuild_cache()
