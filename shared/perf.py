import time

from shared import configuration, repo


def start():
    return time.perf_counter()

def check(start_time, kind, detail, location):
    run_time = time.perf_counter() - start_time
    limit = configuration.get(kind)
    detail_s = detail if isinstance(detail, str) else '; '.join(map(str, list(detail)))
    if limit is not None and run_time > limit:
        msg = 'Exceeded {kind} limit ({run_time} > {limit}) in {location}: {detail_s} ({kind}, {run_time}, {location})'.format(kind=kind, run_time=round(run_time, 1), limit=limit, detail_s=detail_s, location=location)
        repo.create_issue(msg, 'perf', location, 'PennyDreadfulMTG/perf-reports')
