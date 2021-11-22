import logging
from magic import fetcher, multiverse, oracle, whoosh_write
from shared import configuration

logging.basicConfig(level=logging.INFO)

if multiverse.init():
    whoosh_write.reindex()
oracle.init()
try:
    fetcher.sitemap()
except fetcher.FetchException:
    print(f'Config was pointed at {fetcher.decksite_url()}, but it doesnt appear to be listening.')
    for k in ['decksite_hostname', 'decksite_port', 'decksite_protocol']:
        configuration.CONFIG[k] = configuration.DEFAULTS[k]
