"""
Forces a rebuild of the woosh index.
"""
import time

from magic import whoosh_write

REQUIRES_APP_CONTEXT = False

def ad_hoc() -> None:
    start = time.time()
    whoosh_write.reindex()
    end = time.time()
    print('Indexing done in {t} seconds'.format(t=(end - start)))
