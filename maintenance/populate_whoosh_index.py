"""
Forces a rebuild of the whoosh index.
"""
import time

from magic import whoosh_write

REQUIRES_APP_CONTEXT = False

def ad_hoc() -> None:
    start = time.time()
    whoosh_write.reindex()
    end = time.time()
    print(f'Indexing done in {(end - start)} seconds')
