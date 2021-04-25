from decksite.controllers import api
from magic.models import Card

def test_rotation_sort_func():
    cs = [
        Card({'name': 'Sylvan Library', 'hit_in_last_run': True, 'hits': 3}),
        Card({'name': 'Black Lotus', 'hit_in_last_run': True, 'hits': 1}),
        Card({'name': 'Wrenn and Six', 'hit_in_last_run': True, 'hits': 9}),
        Card({'name': 'Abandon Hope', 'hit_in_last_run': True, 'hits': 9}),
        Card({'name': 'Channel', 'hit_in_last_run': False, 'hits': 2}),
        Card({'name': 'Brain in a Jar', 'hit_in_last_run': True, 'hits': 6}),
        Card({'name': 'Firebolt', 'hit_in_last_run': False, 'hits': 4}),
        Card({'name': 'Charming Prince', 'hit_in_last_run': True, 'hits': 8}),
        Card({'name': 'Life from the Loam', 'hit_in_last_run': True, 'hits': 5}),
        Card({'name': 'Fury Charm', 'hit_in_last_run': False, 'hits': 7})
    ]
    num_hit_in_last_run = sum([1 if c.hit_in_last_run else 0 for c in cs])
    f = api.rotation_sort_func('hitInLastRun', 'DESC')
    cs.sort(key=f)
    for i, e in enumerate(cs):
        assert cs[i].hit_in_last_run == (i <= num_hit_in_last_run - 1)
    f = api.rotation_sort_func('hits', 'ASC')
    cs.sort(key=f)
    for i, e in enumerate(cs):
        print("Checking that ", e.name, " has ", i + 1, " hits")
        assert e.hits == i + 1 if i < 9 else 9 # Two cards in the test data have nine hits, the rest have 1…8
    # Check ordering when num hits are the same via the secondary sort on name
    assert cs[8].name == 'Abandon Hope'
    assert cs[9].name == 'Wrenn and Six'
