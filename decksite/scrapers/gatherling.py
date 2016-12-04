import re
import urllib.parse

from bs4 import BeautifulSoup

from magic import fetcher
from shared import dtutil
from shared.pd_exception import InvalidDataException

from decksite.data import competition, deck
from decksite.scrapers import decklist

WINNER = '1st'
SECOND = '2nd'
TOP_4 = 't4'
TOP_8 = 't8'

def scrape():
    soup = BeautifulSoup(fetcher.internal.fetch('http://gatherling.com/eventreport.php?format=Penny+Dreadful&series=&season=&mode=Filter+Events'), 'html.parser')
    tournaments = [(gatherling_url(link['href']), link.string) for link in soup.find_all('a') if link['href'].find('eventreport.php?') >= 0]
    for (url, name) in tournaments:
        tournament(url, name)

def tournament(url, name):
    s = fetcher.internal.fetch(url)

    # Tournament details
    soup = BeautifulSoup(s, 'html.parser')
    report = soup.find('div', {'id': 'EventReport'})
    cell = report.find_all('td')[1]
    date_s = cell.find('br').next.strip() + ' 17:00' # Hack in the known start time because it's not in the page.
    dt = dtutil.parse(date_s, '%d %B %Y %H:%M', dtutil.GATHERLING_TZ)
    competition_id = competition.get_or_insert_competition(dt, dt, name, 'Gatherling', url)

    existing = competition.load_competitions('c.id = {competition_id}'.format(competition_id=competition_id))

    table = soup.find(text='Current Standings').find_parent('table')
    ranks = rankings(table)

    # The HTML of this page is so badly malformed that BeautifulSoup cannot really help us with this bit.
    rows = re.findall('<tr style=">(.*?)</tr>', s, re.MULTILINE | re.DOTALL)
    for row in rows:
        cells = BeautifulSoup(row, 'html.parser').find_all('td')
        tournament_deck(cells, competition_id, dt, ranks)

def rankings(table):
    rows = table.find_all('tr')
    # assert [<td colspan="8"><h6> Penny Dreadful Thursdays 1.02</h6></td>]
    # assert [<td>Rank</td>, <td>Player</td>, <td>Match Points</td>, <td>OMW %</td>, <td>PGW %</td>, <td>OGW %</td>, <td>Matches Played</td>, <td>Byes</td>]

    # [<td colspan="8"><br/><b> Tiebreakers Explained </b><p></p></td>]
    # [<td colspan="8"> Players with the same number of match points are ranked based on three tiebreakers scores according to DCI rules. In order, they are: </td>]
    # [<td colspan="8"> OMW % is the average percentage of matches your opponents have won. </td>]
    # [<td colspan="8"> PGW % is the percentage of games you have won. </td>]
    # [<td colspan="8"> OGW % is the average percentage of games your opponents have won. </td>]
    # [<td colspan="8"> BYEs are not included when calculating standings. For example, a player with one BYE, one win, and one loss has a match win percentage of .50 rather than .66</td>]
    # [<td colspan="8"> When calculating standings, any opponent with less than a .33 win percentage is calculated as .33</td>]

    rows = rows[2:-7]
    ranks = {}
    for row in rows:
        cells = row.find_all('td')
        rank = int(cells[0].string)
        mtgo_username = cells[1].string
        ranks[mtgo_username] = rank
    return ranks

def tournament_deck(cells, competition_id, date, ranks):
    d = {'source': 'Gatherling', 'competition_id': competition_id, 'created_date': dtutil.dt2ts(date)}
    player = cells[2]
    d['mtgo_username'] = player.a.contents[0]
    if player.find('img'):
        img = re.sub(r'styles/Chandra/images/(.*?)\.png', r'\1', player.img['src'])
        if img == WINNER:
            d['finish'] = 1
        elif img == SECOND:
            d['finish'] = 2
        elif img == TOP_4:
            d['finish'] = 3
        elif img == TOP_8:
            d['finish'] = 5
        elif img == 'verified':
            d['finish'] = ranks[d['mtgo_username']]
        else:
            raise InvalidDataException('Unknown player image `{img}`'.format(img=img))
    else:
        d['finish'] = ranks.get(d['mtgo_username'], None)
    parts = cells[3].string.split('-')
    d['wins'] = parts[0]
    d['losses'] = parts[1]
    d['draws'] = 0 if len(parts) < 3 else parts[2]
    link = cells[4].a
    d['url'] = gatherling_url(link['href'])
    d['name'] = link.string
    if cells[5].find('a'):
        d['archetype'] = cells[5].a.string
    else:
        d['archetype'] = cells[5].string
    gatherling_id = urllib.parse.parse_qs(urllib.parse.urlparse(d['url']).query)['id'][0]
    d['identifier'] = gatherling_id
    if deck.get_deck_id(d['source'], d['identifier']) is not None:
        return
    d['cards'] = decklist.parse(fetcher.internal.post(gatherling_url('deckdl.php'), {'id': gatherling_id}))
    deck.add_deck(d)

def gatherling_url(href):
    if href.startswith('http'):
        return href
    return 'http://gatherling.com/{href}'.format(href=href)
