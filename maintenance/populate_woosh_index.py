import time

from magic import multiverse

REQUIRES_APP_CONTEXT = False

def run() -> None:
    start = time.time()
    multiverse.reindex()
    end = time.time()
    print('Indexing done in {t} seconds'.format(t=(end - start)))
