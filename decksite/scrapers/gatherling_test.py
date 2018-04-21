import os

from bs4 import BeautifulSoup

from decksite.data import competition
from decksite.scrapers import gatherling


def test_top_n():
    for n in [4, 8]:
        path = '{path}/gatherling.top{n}.html'.format(path=os.path.dirname(__file__), n=n)
        with open(path, 'r') as f:
            page = f.read()
        soup = BeautifulSoup(page, 'html.parser')
        assert competition.Top(n) == gatherling.find_top_n(soup)

def test_get_dt_and_series():
    dt, competition_series = gatherling.get_dt_and_series('APAC Penny Dreadful Sundays 7.02', '18 February 2018')
    assert dt.strftime('%Y-%m-%d %H:%M') == '2018-02-18 07:00'
    assert competition_series == 'APAC Penny Dreadful Sundays'

    dt, competition_series = gatherling.get_dt_and_series('Penny Dreadful FNM - EU 99.99', '03 January 2020')
    assert dt.strftime('%Y-%m-%d %H:%M') == '2020-01-03 18:30'
    assert competition_series == 'Penny Dreadful FNM - EU'

    dt, competition_series = gatherling.get_dt_and_series('Penny Dreadful Saturdays 1.99', '06 January 2018')
    assert competition_series == 'Penny Dreadful Saturdays'
    assert dt.strftime('%Y-%m-%d %H:%M') == '2018-01-06 18:30'

    dt, competition_series = gatherling.get_dt_and_series('Penny Dreadful Sundays 3.03', '07 January 2018')
    assert competition_series == 'Penny Dreadful Sundays'
    assert dt.strftime('%Y-%m-%d %H:%M') == '2018-01-07 18:30'

    dt, competition_series = gatherling.get_dt_and_series('Penny Dreadful Mondays 1.01', '08 January 2018')
    assert competition_series == 'Penny Dreadful Mondays'
    assert dt.strftime('%Y-%m-%d %H:%M') == '2018-01-09 00:00'

    dt, competition_series = gatherling.get_dt_and_series('Penny Dreadful Thursdays 9.01', '11 January 2018')
    assert competition_series == 'Penny Dreadful Thursdays'
    assert dt.strftime('%Y-%m-%d %H:%M') == '2018-01-12 00:00'
