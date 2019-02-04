from typing import Any, Dict

from decksite.data import competition, deck, top
from magic import decklist
from shared import dtutil, fetcher_internal


def disabled() -> None:
    competitions = fetcher_internal.fetch_json('https://pennydreadfulmagic.com/api/competitions')
    competitions.reverse()
    for c in competitions:
        tournament(c)


def tournament(comp: Dict[str, Any]) -> None:
    comp = fetcher_internal.fetch_json(comp['url'])
    dt = dtutil.ts2dt(comp['start_date'])
    de = dtutil.ts2dt(comp['end_date'])
    competition_id = competition.get_or_insert_competition(dt, de, comp['name'], comp['series_name'], comp['url'], top.Top(comp['top_n']))
    print(f"{comp['name']} = {competition_id}")
    loaded_competition = competition.load_competition(competition_id)
    if loaded_competition.num_decks < comp['num_decks']:
        for d in comp['decks']:
            store_deck(d)

def store_deck(d: Dict[str, Any]) -> deck.Deck:
    d['source'] = d['source_name']
    d['url'] = d['source_url']
    existing = deck.get_deck_id(d['source'], d['identifier'])
    if existing is not None:
        return deck.load_deck(existing)
    print(f'Adding {d["name"]}')
    d['mtgo_username'] = d['person']
    d['cards'] = decklist.unvivify(d)
    return deck.add_deck(d)
