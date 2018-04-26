import time

from magic import multiverse
from shared_web import logger


def run():
    start = time.time()
    multiverse.reindex()
    end = time.time()
    logger.warning('Indexing done in {t} seconds'.format(t=(end - start)))
