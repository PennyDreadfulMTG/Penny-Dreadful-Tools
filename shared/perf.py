from magic import fetcher

def slow(kind, time, detail, location='decksite'):
    msg = 'Slow {kind} ({time}): {detail} ({kind}, {time})'.format(time=round(time, 1), kind=kind, detail=detail)
    print(msg)
    fetcher.create_github_issue(msg, 'perf', location)
