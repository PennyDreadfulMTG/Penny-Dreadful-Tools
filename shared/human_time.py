import datetime

def display_date(dt, granularity=1):
    if (datetime.datetime.utcnow() - dt) > datetime.timedelta(365):
        '{%d %M %YYYY}'.format(dt)
    if (datetime.datetime.utcnow() - dt) > datetime.timedelta(28):
        '{%d %M}'.format(dt)
    else:
        diff = datetime.datetime.utcnow() - dt
        return '{duration} ago'.format(duration=display_time(diff.total_seconds(), granularity))

def display_time(seconds, granularity=2):
    intervals = (
        ('weeks', 60 * 60 * 24 * 7),
        ('days', 60 * 60 * 24),
        ('hours', 60 * 60),
        ('minutes', 60),
        ('seconds', 1)
    )
    result = []
    for name, count in intervals:
        value = seconds // count
        if value:
            seconds -= value * count
            if value == 1:
                name = name.rstrip('s')
            result.append("{} {}".format(round(value), name))
        else:
            # Add a blank if we're in the middle of other values
            if len(result) > 0:
                result.append(None)
    return ', '.join([x for x in result[:granularity] if x is not None])
