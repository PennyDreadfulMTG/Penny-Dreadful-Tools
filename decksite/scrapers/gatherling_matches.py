from decksite.data import deck
from decksite.scrapers import gatherling
from shared_web import logger

# Script to scrape match results without scraping decklists so we can backfill all Gatherling results without rescraping decks.

def scrape(ignore_competition_ids=None):
    if ignore_competition_ids is None:
        ignore_competition_ids = []
    where = "d.id NOT IN (SELECT deck_id FROM deck_match) AND d.source_id = (SELECT id FROM source WHERE name = 'Gatherling')"
    if ignore_competition_ids:
        where += ' AND d.competition_id NOT IN ({ids})'.format(ids=', '.join([str(id) for id in ignore_competition_ids]))
    decks = deck.load_decks(where, order_by='d.competition_id')
    if len(decks) == 0:
        logger.warning('No more competitions to insert matches for.')
        return
    ds, competition_id = [], decks[0].competition_id
    for d in decks:
        if d.competition_id != competition_id:
            # Arbitrary cutoff of number of decks to say "these are decks with no matches not a full unlogged competition".
            if len(ds) >= 4:
                break
            else:
                logger.warning('Skipping {id} because deck count is {n}.'.format(id=competition_id, n=len(ds)))
                ds = []
                competition_id = d.competition_id
        ds.append(d)
    matches = []
    for d in ds:
        matches += gatherling.tournament_matches(d)
    if len(matches) == 0:
        logger.warning('Found no matches in {id} so trying the next competition.'.format(id=competition_id))
        scrape(ignore_competition_ids + [competition_id])
    gatherling.add_ids(matches, ds)
    gatherling.insert_matches_without_dupes(ds[0].created_date, matches)
