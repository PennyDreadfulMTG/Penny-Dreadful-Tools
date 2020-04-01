from typing import Optional

from magic import fetcher
from magic.models import Card
from shared import dtutil
from shared.fetch_tools import FetchException

MAX_PRICE_CENTS = 2
MAX_PRICE_TIX = MAX_PRICE_CENTS / 100
MAX_PRICE_TEXT = '2¢'

def card_price_string(card: Card, short: bool = False) -> str:
    def price_info(c: Card) -> str:
        try:
            p = fetcher.card_price(c.name)
        except FetchException:
            return 'Price unavailable'
        if p is None:
            return 'Not available online'
        # Currently disabled
        s = '{price}'.format(price=format_price(p['price']))
        try:
            if float(p['low']) <= 0.05:
                s += ' (low {low}, high {high}'.format(low=format_price(p['low']), high=format_price(p['high']))
                if float(p['low']) <= MAX_PRICE_TIX and not short:
                    s += ', {week}% this week, {month}% this month, {season}% this season'.format(week=round(float(p['week']) * 100.0), month=round(float(p['month']) * 100.0), season=round(float(p['season']) * 100.0))
                s += ')'
            age = dtutil.dt2ts(dtutil.now()) - p['time']
            if age > 60 * 60 * 2:
                s += '\nWARNING: price information is {display} old'.format(display=dtutil.display_time(age, 1))
        except TypeError as e:
            print(f'Unable to get price info string from {p} because of {e}')
            return 'Price information is incomplete'
        return s
    def format_price(p: Optional[str]) -> str:
        if p is None:
            return 'Unknown'
        dollars, cents = str(round(float(p), 2)).split('.')
        return '{dollars}.{cents}'.format(dollars=dollars, cents=cents.ljust(2, '0'))
    return price_info(card)
