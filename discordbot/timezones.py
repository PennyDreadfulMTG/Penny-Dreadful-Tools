import datetime
import re

import pytz

from discordbot import geonames
from shared import dtutil
from shared.pd_exception import TooFewItemsException


def current_time(timezone: datetime.tzinfo, twentyfour: bool) -> str:
    if twentyfour:
        return dtutil.now(timezone).strftime('%H:%M')
    try:
        return dtutil.now(timezone).strftime('%l:%M %p')
    except ValueError:  # %l is not a universally supported argument. Fall back to %I on other platforms.
        return dtutil.now(timezone).strftime('%I:%M %p')


def time(query: str, twentyfour: bool) -> dict[str, list[str]]:
    query = query.strip()
    if not query:
        raise TooFewItemsException('No location provided')
    offset = times_from_utc_offset(query, twentyfour)
    if offset is not None:
        return offset
    if '/' in query:
        return times_from_timezone_name(query, twentyfour)
    if re.fullmatch(r'[A-Za-z]{2,6}', query):
        try:
            return times_from_timezone_code(query, twentyfour)
        except TooFewItemsException:
            pass
    return times_from_location(query, twentyfour)


def times_from_timezone_name(query: str, twentyfour: bool) -> dict[str, list[str]]:
    possible = next((name for name in pytz.all_timezones if name.casefold() == query.casefold()), None)
    if possible is None:
        raise TooFewItemsException(f'Not a recognized timezone: {query}')
    timezone = dtutil.timezone(possible)
    return {current_time(timezone, twentyfour): [possible]}


def times_from_utc_offset(query: str, twentyfour: bool) -> dict[str, list[str]] | None:
    if query.upper() in {'UTC', 'GMT'}:
        return {current_time(datetime.UTC, twentyfour): [query.upper()]}
    match = re.fullmatch(r'(?:UTC|GMT)\s*([+-])\s*(\d{1,2})(?::?(\d{2}))?', query, re.IGNORECASE)
    if match is None:
        return None
    hours = int(match.group(2))
    minutes = int(match.group(3) or 0)
    if hours > 14 or minutes > 59 or (hours == 14 and minutes != 0):
        raise TooFewItemsException(f'Not a valid UTC offset: {query}')
    sign = 1 if match.group(1) == '+' else -1
    offset = datetime.timedelta(hours=hours, minutes=minutes) * sign
    label = f'UTC{match.group(1)}{hours:02d}' + (f':{minutes:02d}' if minutes else '')
    timezone = datetime.timezone(offset, name=label)
    return {current_time(timezone, twentyfour): [label]}


def times_from_timezone_code(query: str, twentyfour: bool) -> dict[str, list[str]]:
    possibles = [name for name in pytz.common_timezones if datetime.datetime.now(pytz.timezone(name)).strftime('%Z') == query.upper()]
    if not possibles:
        raise TooFewItemsException(f'Not a recognized timezone: {query.upper()}')
    results: dict[str, list[str]] = {}
    for possible in possibles:
        timezone = dtutil.timezone(possible)
        value = current_time(timezone, twentyfour)
        results[value] = results.get(value, []) + [possible]
    return results


def times_from_location(query: str, twentyfour: bool) -> dict[str, list[str]]:
    place = geonames.find(query)
    if place is None:
        raise TooFewItemsException(f'No populated place found for {query}')
    timezone = dtutil.timezone(place.timezone)
    return {current_time(timezone, twentyfour): [place.display_name]}
