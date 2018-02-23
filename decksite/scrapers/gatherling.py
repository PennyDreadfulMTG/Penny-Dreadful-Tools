import re
import urllib.parse

from bs4 import BeautifulSoup

from decksite.data import competition, deck, match
from decksite.database import db
from decksite.scrapers import decklist
from magic import fetcher
from shared import dtutil
from shared.pd_exception import InvalidDataException

WINNER = '1st'
SECOND = '2nd'
TOP_4 = 't4'
TOP_8 = 't8'

def scrape(limit=50):
    soup = BeautifulSoup(fetcher.internal.fetch('https://gatherling.com/eventreport.php?format=Penny+Dreadful&series=&season=&mode=Filter+Events', character_encoding='utf-8'), 'html.parser')
    tournaments = [(gatherling_url(link['href']), link.string) for link in soup.find_all('a') if link['href'].find('eventreport.php?') >= 0]
    n = 0
    for (url, name) in tournaments:
        i = tournament(url, name)
        n = n + i
        if i > limit:
            return

def tournament(url, name):
    s = fetcher.internal.fetch(url, character_encoding='utf-8')

    # Tournament details
    soup = BeautifulSoup(s, 'html.parser')
    cell = soup.find('div', {'id': 'EventReport'}).find_all('td')[1]
    # Hack in the known start time because it's not in the page.
    start_time = '19:00'
    name = cell.find('a').string.strip()
    if 'Saturday' in name or 'Sunday' in name or 'PDS' in name:
        start_time = '13:30'
    date_s = cell.find('br').next.strip() + ' {start_time}'.format(start_time=start_time)
    if '-0001' in date_s:
        # Tournament has been incorrectly configured.
        return 0

    dt = dtutil.parse(date_s, '%d %B %Y %H:%M', dtutil.GATHERLING_TZ)
    competition_id = competition.get_or_insert_competition(dt, dt, name, 'Penny Dreadful {day}s'.format(day=dtutil.day_of_week(dt, dtutil.GATHERLING_TZ)), url)
    table = soup.find(text='Current Standings').find_parent('table')
    ranks = rankings(table)

    return add_decks(dt, competition_id, ranks, s)

def add_decks(dt, competition_id, ranks, s):
    # The HTML of this page is so badly malformed that BeautifulSoup cannot really help us with this bit.
    rows = re.findall('<tr style=">(.*?)</tr>', s, re.MULTILINE | re.DOTALL)
    decks_added, matches, ds = 0, [], []
    for row in rows:
        cells = BeautifulSoup(row, 'html.parser').find_all('td')
        d = tournament_deck(cells, competition_id, dt, ranks)
        if d is not None:
            decks_added += 1
            ds.append(d)
            matches += tournament_matches(d)
    add_ids(matches, ds)
    insert_matches_without_dupes(dt, matches)
    return decks_added

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
            d['finish'] = ranks.get(d['mtgo_username'], None)
        else:
            raise InvalidDataException('Unknown player image `{img}`'.format(img=img))
    else:
        d['finish'] = ranks.get(d['mtgo_username'], None)
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
        return None
    d['cards'] = decklist.parse(fetcher.internal.post(gatherling_url('deckdl.php'), {'id': gatherling_id}))
    if len(d['cards']) == 0:
        print('Rejecting deck with id {id} because it has no cards.'.format(id=gatherling_id))
        return None
    return deck.add_deck(d)

def tournament_matches(d):
    url = 'https://gatherling.com/deck.php?mode=view&id={identifier}'.format(identifier=d.identifier)
    s = fetcher.internal.fetch(url, character_encoding='utf-8')
    soup = BeautifulSoup(s, 'html.parser')
    anchor = soup.find(string='MATCHUPS')
    if anchor is None:
        print('Skipping {id} because it has no MATCHUPS.'.format(id=d.id))
        return []
    table = anchor.findParents('table')[0]
    rows = table.find_all('tr')
    rows.pop(0) # skip header
    rows.pop() # skip empty last row
    return find_matches(d, rows)

def find_matches(d, rows):
    matches = []
    for row in rows:
        tds = row.find_all('td')
        if 'No matches were found for this deck' in tds[0].renderContents().decode('utf-8'):
            print('Skipping {identifier} because it played no matches.'.format(identifier=d.identifier))
            break
        round_type, num = re.findall(r'([TR])(\d+)', tds[0].string)[0]
        num = int(num)
        if round_type == 'R':
            elimination = 0
            round_num = num
        elif round_type == 'T':
            elimination = num
            round_num += 1
        else:
            raise InvalidDataException('Round was neither Swiss (R) nor Top 4/8 (T) in {round_type} for {id}'.format(round_type=round_type, id=d.id))
        if 'Bye' in tds[1].renderContents().decode('utf-8') or 'No Deck Found' in tds[5].renderContents().decode('utf-8'):
            left_games, right_games, right_identifier = 2, 0, None
        else:
            left_games, right_games = tds[2].string.split(' - ')
            href = tds[5].find('a')['href']
            right_identifier = re.findall(r'id=(\d+)', href)[0]
        matches.append({
            'round': round_num,
            'elimination': elimination,
            'left_games': left_games,
            'left_identifier': d.identifier,
            'right_games': right_games,
            'right_identifier': right_identifier
        })
    return matches

def insert_matches_without_dupes(dt, matches):
    db().begin()
    inserted = {}
    for m in matches:
        reverse_key = str(m['round']) + '|' + str(m['right_id']) + '|' + str(m['left_id'])
        if inserted.get(reverse_key):
            continue
        match.insert_match(dt, m['left_id'], m['left_games'], m['right_id'], m['right_games'], m['round'], m['elimination'])
        key = str(m['round']) + '|' + str(m['left_id']) + '|' + str(m['right_id'])
        inserted[key] = True
    db().commit()

def add_ids(matches, ds):
    decks_by_identifier = {d.identifier: d for d in ds}
    for m in matches:
        m['left_id'] = decks_by_identifier[m['left_identifier']].id
        m['right_id'] = decks_by_identifier[m['right_identifier']].id if m['right_identifier'] else None

def gatherling_url(href):
    if href.startswith('http'):
        return href
    return 'https://gatherling.com/{href}'.format(href=href)
