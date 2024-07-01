from magic import fetcher
from shared import configuration
from shared.pd_exception import TooFewItemsException

DAILY = True
REQUIRES_APP_CONTEXT = False


# Update the list of cards that should be returned when is:spikey is searched for.
def run() -> None:
    n, names, _cards = fetcher.search_scryfall('is:spikey', exhaustive=True)
    if n < 482:  # 482 was the count of is:spikey when I wrote this in April 2024. Just a little sanity check.
        raise TooFewItemsException(f"There were only {n} is:spikey results so I'm not going to overwrite the file")
    with open(configuration.is_spikey_file.get(), 'w') as f:
        f.write('\n'.join(names) + '\n')
