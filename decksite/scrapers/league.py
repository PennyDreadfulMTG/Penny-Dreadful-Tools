import csv
import random
import string

from pytz import timezone

from shared import dtutil

from decksite import league
from decksite.data import deck
from decksite.database import db
from decksite.scrapers import decklist

# One-off importer for previous league decklists.
# File, Download As..., CSV from Google docs.

def scrape():
    for n in [1, 2, 3]:
        try:
            import_file('league{n}.csv'.format(n=n))
            update_results('league{n}-results.csv'.format(n=n))
        except FileNotFoundError:
            print('Skipping {n} because not found.'.format(n=n))

def import_file(file):
    count = {}
    with open(file, newline='') as csvfile:
        reader = csv.reader(csvfile, delimiter=',', quotechar='"')
        header_line = next(reader)
        has_deck_names = header_line[3] == 'Decklist Name'
        for row in reader:
            date_s = row[0]
            date = dtutil.parse(date_s, '%m/%d/%Y %H:%M:%S', timezone('America/New_York'))
            mtgo_username = row[1]
            count[mtgo_username] = count.get(mtgo_username, 0) + 1
            decklist_s = row[2]
            if has_deck_names:
                name = row[3]
            else:
                name = '{mtgo_username} League Deck {count}'.format(mtgo_username=mtgo_username, count=count[mtgo_username])
            d = {}
            d['mtgo_username'] = mtgo_username
            d['name'] = name
            d['cards'] = decklist.parse(decklist_s.strip('"'))
            d['source'] = 'League'
            d['created_date'] = dtutil.dt2ts(date)
            d['url'] = 'http://pennydreadfulmagic.com/'
            if file == 'league1.csv':
                d['competition_id'] = db().value("SELECT id FROM competition WHERE name = 'League September 2016'")
            if file == 'league2.csv':
                d['competition_id'] = db().value("SELECT id FROM competition WHERE name = 'League October 2016'")
            if file == 'league3.csv':
                d['competition_id'] = db().value("SELECT id FROM competition WHERE name = 'League November 2016'")
            d['identifier'] = league.identifier(d)
            deck.add_deck(d)

# pylint: disable=too-many-locals
def update_results(file):
    if file == 'league1-results.csv':
        competition_id = db().value("SELECT id FROM competition WHERE name = 'League September 2016'")
    if file == 'league2-results.csv':
        competition_id = db().value("SELECT id FROM competition WHERE name = 'League October 2016'")
    if file == 'league3-results.csv':
        competition_id = db().value("SELECT id FROM competition WHERE name = 'League November 2016'")
    with open(file, newline='') as csvfile:
        reader = csv.reader(csvfile, delimiter=',', quotechar='"')
        header_line = next(reader)
        has_deck_names = header_line[2] == 'Decklist Name'
        results = {}
        for row in reader:
            if row[0] == '':
                break
            mtgo_username = row[1]
            modifier = 1 if has_deck_names else 0
            wins = int(row[2 + modifier])
            losses = int(row[3 + modifier])
            if mtgo_username not in results:
                results[mtgo_username] = []
            results[mtgo_username].append((wins, losses))
        for mtgo_username, records in results.items():
            sql = 'SELECT id FROM deck WHERE person_id = (SELECT id FROM person WHERE mtgo_username = ?) AND competition_id = ? ORDER BY created_date'
            deck_ids = db().values(sql, [mtgo_username, competition_id])
            for deck_id in deck_ids:
                wins, losses = records.pop(0)
                sql = 'UPDATE deck SET wins = ?, losses = ?, draws = 0 WHERE id = ?'
                db().execute(sql, [wins, losses, deck_id])
