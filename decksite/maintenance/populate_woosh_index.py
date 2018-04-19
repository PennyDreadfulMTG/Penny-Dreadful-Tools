import time

from decksite import logger
from magic import multiverse


def run():
    start = time.time()
    multiverse.reindex()
    end = time.time()
    logger.warning('Indexing done in {t} seconds'.format(t=(end - start)))
