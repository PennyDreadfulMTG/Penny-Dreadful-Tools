import time

from magic import multiverse


def run():
    start = time.time()
    multiverse.reindex()
    end = time.time()
    print("Indexing done in {t} seconds".format(t=(end - start)))
