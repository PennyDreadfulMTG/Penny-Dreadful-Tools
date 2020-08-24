import datetime
import sys

from decksite.data import deck
from decksite.database import db
from magic import fetcher
from magic.whoosh_search import WhooshSearcher
from shared import dtutil


def ad_hoc() -> None:
    try:
        start = dtutil.parse(sys.argv[2], '%Y-%m-%d', dtutil.GATHERLING_TZ)
    except (IndexError, TypeError, ValueError):
        start = dtutil.now() - datetime.timedelta(days=7)
    print(f'Checking all Gatherling decks from {start}. To check from a different date supply it as a commandline arg in the form YYYY-MM-DD')
    decks = deck.load_decks(f"d.created_date >= UNIX_TIMESTAMP('{start}') AND ct.name = 'Gatherling'")
    print(f'Found {len(decks)} decks.')
    searcher = WhooshSearcher()
    for d in decks:
        comments = fetcher.gatherling_deck_comments(d.identifier)
        for c in comments:
            if '=' not in c:
                print(f'Ignoring {c}')
                continue
            print(c)
            best_match_f = lambda s: searcher.search(s.strip()).get_best_match()
            placeholder, real = map(best_match_f, c.split('='))
            print(f'I think this means replace {placeholder} with {real}. Go ahead? (Y/n)')
            answer = input()
            if answer == '' or answer.lower() == 'y':
                rows_affected = db().execute('UPDATE deck_card SET card = %s WHERE deck_id = %s AND card = %s', [real, d.id, placeholder])
                print(f'{rows_affected} rows were updated.')
