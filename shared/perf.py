import time
from typing import Any

from shared import configuration, repo


def start() -> float:
    return time.perf_counter()

def check(start_time: float, kind: str, detail: Any, location: str) -> None:
    run_time = time.perf_counter() - start_time
    limit = configuration.get_float(kind)
    detail_s = detail if isinstance(detail, str) else '; '.join(map(str, list(detail)))
    if limit is not None and run_time > limit:
        msg = 'Exceeded {kind} limit ({run_time} > {limit}) in {location}: {detail_s} ({kind}, {run_time}, {location})'.format(kind=kind, run_time=round(run_time, 1), limit=limit, detail_s=detail_s, location=location)
        repo.create_issue(msg, 'perf', location, 'PennyDreadfulMTG/perf-reports')

def test(f, limit) -> None:
    begin = time.perf_counter()
    f()
    duration = time.perf_counter() - begin
    print(duration)
    assert duration <= limit
