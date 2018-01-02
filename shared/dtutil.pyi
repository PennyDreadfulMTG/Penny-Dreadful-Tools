# make_stub_files: Sun 31 Dec 2017 at 16:46:32
from typing import Any, Dict, Optional, Sequence, Tuple, Union
def ts2dt(ts: Any) -> Any: ...
    #   0: return pytz.timezone('UTC').localize(datetime.datetime.utcfromtimestamp(ts))
    # ? 0: return pytz.timezone(str).localize(datetime.datetime.utcfromtimestamp(ts))
def dt2ts(dt: Any) -> Any: ...
    #   0: return dt.timestamp()
    # ? 0: return dt.timestamp()
def parse(s: Any, date_format: Any, tz: Any) -> Any: ...
    #   0: return tz.localize(dt).astimezone(pytz.timezone('UTC'))
    # ? 0: return tz.localize(dt).astimezone(pytz.timezone(str))
def parse_to_ts(s: Any, date_format: Any, tz: Any) -> Any: ...
    #   0: return dt2ts(dt)
    # ? 0: return dt2ts(dt)
def timezone(tzid: Any) -> Any: ...
    #   0: return pytz.timezone(tzid)
    # ? 0: return pytz.timezone(tzid)
def now(tz: Any=None) -> Any: ...
    #   0: return datetime.datetime.now(tz)
    # ? 0: return datetime.datetime.now(tz)
def day_of_week(dt: Any, tz: Any) -> Any: ...
    #   0: return dt.astimezone(tz).strftime('%A')
    # ? 0: return dt.astimezone(tz).strftime(str)
def display_date(dt: Any, granularity: Any=1) -> Union[Any, str]: ...
    #   0: return replace_day_with_ordinal(s)
    # ? 0: return replace_day_with_ordinal(s)
    #   1: return replace_day_with_ordinal(s)
    # ? 1: return replace_day_with_ordinal(s)
    #   2: return 'just now'
    #   2: return str
    #   3: return '{duration} {suffix}'.format(duration=display_time(diff,granularity),suffix=suffix)
    # ? 3: return str.format(duration=display_time(diff, granularity), suffix=suffix)
def replace_day_with_ordinal(s: Any) -> Any: ...
    #   0: return re.sub('_(.*)_',day2ordinal,s)
    # ? 0: return re.sub(str, day2ordinal, s)
def day2ordinal(m: Any) -> Any: ...
    #   0: return p.ordinal(int(m.group(1)))
    # ? 0: return p.ordinal(int(m.group(number)))
def display_time(seconds: Any, granularity: int) -> str: ...
    #   0: return 'now'
    #   0: return str
    #   1: return ', '.join('{} {}'.format(value,unit.rstrip('s') if value==1 else unit ) for (value, unit) in result[:granularity] if value>0)
    # ? 1: return str.join(str.format(value, Any) for Tuple[value, unit] in result[:granularity] if bool)
