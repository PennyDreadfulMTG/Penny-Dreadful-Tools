import sys
import time

from magic import fetcher
from shared import configuration

def start():
    return time.perf_counter()

def check(start_time, kind, detail, location):
    run_time = time.perf_counter() - start_time
    limit = configuration.get(kind)
    if limit is not None and run_time > limit:
        msg = 'Exceeded {kind} limit ({run_time} > {limit}) in {location}: {detail} ({kind}, {run_time}, {location})'.format(kind=kind, run_time=round(run_time, 1), limit=limit, detail='; '.join(map(str, list(detail))), location=location)
        print(msg)
        fetcher.create_github_issue(msg, 'perf', location)
