import time
from typing import Any, Callable

from flask import current_app

from shared import configuration, repo


def start() -> float:
    return time.perf_counter()

def check(start_time: float, kind: str, detail: Any, location: str) -> None:
    run_time = time.perf_counter() - start_time
    limit = configuration.get_float(kind)
    if limit is not None and run_time > limit:
        detail_s = detail if isinstance(detail, str) else '\n\n'.join(map(str, list(detail)))
        msg = 'Exceeded {kind} limit ({run_time} > {limit}) in {location}: {detail_s} ({kind}, {run_time}, {location})'.format(kind=kind, run_time=round(run_time, 1), limit=limit, detail_s=detail_s, location=location)
        try:
            flask_location = current_app.name
        except RuntimeError: # Working outside of application context
            flask_location = ''
        repo.create_issue(msg, f'{location}-perf', flask_location or location, 'PennyDreadfulMTG/perf-reports')

def test(f: Callable, limit: float) -> None:
    begin = time.perf_counter()
    f()
    duration = time.perf_counter() - begin
    print(duration)
    assert duration <= limit

def took(start_time: float) -> float:
    return time.perf_counter() - start_time
