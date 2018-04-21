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
