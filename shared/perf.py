import time

from flask import request, session

from shared import configuration, repo

def start():
    return time.perf_counter()

def check(start_time, kind, detail, location):
    run_time = time.perf_counter() - start_time
    limit = configuration.get(kind)
    detail_s = detail if isinstance(detail, str) else '; '.join(map(str, list(detail)))
    if limit is not None and run_time > limit:
        msg = 'Exceeded {kind} limit ({run_time} > {limit}) in {location}: {detail_s} ({kind}, {run_time}, {location})'.format(kind=kind, run_time=round(run_time, 1), limit=limit, detail_s=detail_s, location=location)
        if request:
            msg += """
                Request Method: {method}
                Path: {full_path}
                Cookies: {cookies}
                Endpoint: {endpoint}
                View Args: {view_args}
                Person: {id}
                User-Agent: {user_agent}
                Referrer: {referrer}
            """.format(method=request.method, full_path=request.full_path, cookies=request.cookies, endpoint=request.endpoint, view_args=request.view_args, id=session.get('id', 'logged_out'), user_agent=request.headers.get('User-Agent'), referrer=request.referrer)
        print(msg)
        repo.create_issue(msg, 'perf', location, 'PennyDreadfulMTG/perf-reports')
