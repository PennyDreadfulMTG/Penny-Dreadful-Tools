import datetime
import re
import urllib.parse

from bs4 import BeautifulSoup

from magic import fetcher

from decksite.data import competition, deck
from decksite.scrapers import decklist

WINNER = '1st'
SECOND = '2nd'
TOP_4 = 't4'
TOP_8 = 't8'

def scrape():
    soup = BeautifulSoup(fetcher.fetch('http://gatherling.com/eventreport.php?format=Penny+Dreadful&series=&season=&mode=Filter+Events'), 'html.parser')
    tournaments = [(gatherling_url(link['href']), link.string) for link in soup.find_all('a') if link['href'].find('eventreport.php?') >= 0]
    for (url, name) in tournaments:
        tournament(url, name)

def tournament(url, name):
    s = fetcher.fetch(url)

    # Tournament details
    soup = BeautifulSoup(s, 'html.parser')
    report = soup.find('div', {'id': 'EventReport'})
    cell = report.find_all('td')[1]
    date_s = cell.find('br').next.strip()
    dt = datetime.datetime.strptime(date_s, '%d %B %Y')
    competition_id = competition.get_or_insert_competition(dt, dt, name, 'Gatherling')

    # The HTML of this page is so badly malformed that BeautifulSoup cannot really help us with this bit.
    rows = re.findall('<tr style=">(.*?)</tr>', s, re.MULTILINE | re.DOTALL)
    for row in rows:
        cells = BeautifulSoup(row, 'html.parser').find_all('td')
        tournament_deck(cells, competition_id)

def tournament_deck(cells, competition_id):
    d = {'source': 'Gatherling', 'competition_id': competition_id}
    player = cells[2]
    d['mtgo_username'] = player.a.contents[0]
    d['wins'], d['losses'] = cells[3].string.split('-')
    link = cells[4].a
    d['url'] = gatherling_url(link['href'])
    d['name'] = link.string
    if cells[5].find('a'):
        d['archetype'] = cells[5].a.string
    else:
        d['archetype'] = cells[5].string
    gatherling_id = urllib.parse.parse_qs(urllib.parse.urlparse(d['url']).query)['id'][0]
    d['identifier'] = gatherling_id
    d['cards'] = decklist.parse(fetcher.post(gatherling_url('deckdl.php'), {'id': gatherling_id}))
    deck.add_deck(d)

def gatherling_url(href):
    if href.startswith('http'):
        return href
    return 'http://gatherling.com/{href}'.format(href=href)
