import pytest

from magic import rotation
from magic.models import Card


def test_hits_needed_score() -> None:
    assert rotation.hits_needed_score(Card({'name': 'Test', 'status': 'Undecided', 'hits': 33})) == 135
    assert rotation.hits_needed_score(Card({'name': 'Test', 'status': 'Undecided', 'hits': 1})) == 167
    assert rotation.hits_needed_score(Card({'name': 'Test', 'status': 'Legal', 'hits': 84})) == 252
    assert rotation.hits_needed_score(Card({'name': 'Test', 'status': 'Legal', 'hits': 130})) == 298
    assert rotation.hits_needed_score(Card({'name': 'Test', 'status': 'Legal', 'hits': 168})) == 336
    assert rotation.hits_needed_score(Card({'name': 'Test', 'status': 'Not Legal', 'hits': 83})) == 421
    assert rotation.hits_needed_score(Card({'name': 'Test', 'status': 'Not Legal', 'hits': 1})) == 503

def test_rotation_sort_func() -> None:
    # First, set up the test data we are going to use. An imaginary scenario 120 runs in to the rotation process.
    num_runs_so_far = 120
    remaining_runs = rotation.TOTAL_RUNS - num_runs_so_far
    target = rotation.TOTAL_RUNS / 2
    cs = [
        Card({'name': 'Sylvan Library', 'hit_in_last_run': True, 'hits': 30}),
        Card({'name': 'Black Lotus', 'hit_in_last_run': True, 'hits': 10}),
        Card({'name': 'Murderous Cut', 'hit_in_last_run': False, 'hits': 90}),
        Card({'name': 'Wrenn and Six', 'hit_in_last_run': True, 'hits': 90}),
        Card({'name': 'Abandon Hope', 'hit_in_last_run': True, 'hits': 90}),
        Card({'name': 'Channel', 'hit_in_last_run': False, 'hits': 20}),
        Card({'name': 'Brain in a Jar', 'hit_in_last_run': True, 'hits': 60}),
        Card({'name': 'Firebolt', 'hit_in_last_run': False, 'hits': 40}),
        Card({'name': 'Charming Prince', 'hit_in_last_run': True, 'hits': 80}),
        Card({'name': 'Life from the Loam', 'hit_in_last_run': True, 'hits': 50}),
        Card({'name': 'Fury Charm', 'hit_in_last_run': False, 'hits': 70}),
        Card({'name': 'Dark Confidant', 'hit_in_last_run': True, 'hits': 100}),
        Card({'name': 'Colossal Dreadmaw', 'hit_in_last_run': True, 'hits': 1}),
    ]
    for c in cs:
        c.hits_needed = max(target - c.hits, 0)
        c.percent_needed = str(round(round(c.hits_needed / remaining_runs, 2) * 100))
        if c.hits_needed == 0:
            c.status = 'Legal'
        elif c.hits_needed < remaining_runs:
            c.status = 'Undecided'
        else:
            c.status = 'Not Legal'

    rotation.rotation_sort(cs, 'hitInLastRun', 'DESC')
    # Hit in last run and still possible to make it, but not yet confirmed, most hits first.
    assert cs[0].name == 'Charming Prince'
    assert cs[1].name == 'Brain in a Jar'
    assert cs[2].name == 'Life from the Loam'
    # Followed by hit in last run and confirmed, least hits first.
    assert cs[3].name == 'Abandon Hope'
    assert cs[4].name == 'Wrenn and Six'
    assert cs[5].name == 'Dark Confidant'
    # Hit in last run but eliminated, most hits first.
    assert cs[6].name == 'Sylvan Library'
    assert cs[7].name == 'Black Lotus'
    assert cs[8].name == 'Colossal Dreadmaw'
    # No hit in last run but still possible to make it, most hits first.
    assert cs[9].name == 'Fury Charm'
    assert cs[10].name == 'Firebolt'
    # No hit in last run but confirmed, least hits first
    assert cs[11].name == 'Murderous Cut'
    # No hit in last run, confirmed out, most hits first.
    assert cs[12].name == 'Channel'

    rotation.rotation_sort(cs, 'hits', 'DESC')
    assert cs[0].name == 'Dark Confidant'
    assert cs[1].name == 'Abandon Hope'
    assert cs[2].name == 'Murderous Cut'
    assert cs[3].name == 'Wrenn and Six'
    assert cs[4].name == 'Charming Prince'
    assert cs[5].name == 'Fury Charm'
    assert cs[6].name == 'Brain in a Jar'
    assert cs[7].name == 'Life from the Loam'
    assert cs[8].name == 'Firebolt'
    assert cs[9].name == 'Sylvan Library'
    assert cs[10].name == 'Channel'
    assert cs[11].name == 'Black Lotus'
    assert cs[12].name == 'Colossal Dreadmaw'

    rotation.rotation_sort(cs, 'hitsNeeded', 'ASC')
    # First we expect the cards that are nearly there, closest first.
    assert cs[0].name == 'Charming Prince'  # 80 / 120
    assert cs[1].name == 'Fury Charm'       # 70 / 120
    assert cs[2].name == 'Brain in a Jar'   # …
    assert cs[3].name == 'Life from the Loam'
    assert cs[4].name == 'Firebolt'
    # Then cards that have made it, least hits first, to maximize the chance of showing cards that recently made it in near the top.
    assert cs[5].name == 'Abandon Hope'
    assert cs[6].name == 'Murderous Cut'
    assert cs[7].name == 'Wrenn and Six'
    assert cs[8].name == 'Dark Confidant'
    # Then cards that have been eliminated, most hits first.
    assert cs[9].name == 'Sylvan Library'
    assert cs[10].name == 'Channel'
    assert cs[11].name == 'Black Lotus'
    assert cs[12].name == 'Colossal Dreadmaw'

    rotation.rotation_sort(cs, 'name', 'ASC')
    assert cs[0].name == 'Abandon Hope'
    assert cs[1].name == 'Black Lotus'
    assert cs[2].name == 'Brain in a Jar'
    assert cs[3].name == 'Channel'
    assert cs[4].name == 'Charming Prince'
    assert cs[5].name == 'Colossal Dreadmaw'
    assert cs[6].name == 'Dark Confidant'
    assert cs[7].name == 'Firebolt'
    assert cs[8].name == 'Fury Charm'
    assert cs[9].name == 'Life from the Loam'
    assert cs[10].name == 'Murderous Cut'
    assert cs[11].name == 'Sylvan Library'
    assert cs[12].name == 'Wrenn and Six'

@pytest.mark.functional
def test_list_of_most_interesting() -> None:
    never_before_legal_cards = [
        Card({'name': 'Mox Jet'}),
        Card({'name': 'Black Lotus'}),
    ]
    super_playable_card = Card({'name': 'Counterspell'})
    somewhat_playable_card = Card({'name': 'Fling'})

    s = rotation.list_of_most_interesting(never_before_legal_cards + [super_playable_card, somewhat_playable_card])
    good_cards = 'Black Lotus, Mox Jet, Counterspell, Fling'
    assert s == good_cards

    garbage_cards = [
        Card({'name': 'Zombie Goliath'}),
        Card({'name': 'Wild Certaok'}),
        Card({'name': 'Moss Monster'}),
        Card({'name': 'Nessian Courser'}),
        Card({'name': 'Nettle Swine'}),
        Card({'name': 'Ogre Resister'}),
        Card({'name': 'Python'}),
        Card({'name': 'Redwood Treefolk'}),
        Card({'name': 'Renegade Demon'}),
        Card({'name': 'Russet Wolves'}),
        Card({'name': 'Spined Wurm'}),
        Card({'name': 'Thraben Purebloods'}),
        Card({'name': 'Vampire Noble'}),
        Card({'name': 'Undead Minotaur'}),
        Card({'name': 'Vastwood Gorger'}),
        Card({'name': 'Warpath Ghoul'}),
        Card({'name': 'Colossodon Yearling'}),
        Card({'name': 'Curio Vendor'}),
        Card({'name': 'Devilthorn Fox'}),
        Card({'name': 'Cyclops of One-Eyed Pass'}),
        Card({'name': 'Fomori Nomad'}),
        Card({'name': 'Hexplate Golem'}),
        Card({'name': 'Jwari Scuttler'}),
        Card({'name': 'Krovikan Scoundrel'}),
    ]

    cs = never_before_legal_cards + [super_playable_card, somewhat_playable_card] + garbage_cards
    s = rotation.list_of_most_interesting(cs)
    assert s.startswith(good_cards)
    excess = len(cs) - 25
    assert s.endswith(f'and {excess} more')
    assert s.count(',') == 24
    cs = never_before_legal_cards + [super_playable_card, somewhat_playable_card] + garbage_cards
    s2 = rotation.list_of_most_interesting(cs)
    assert s == s2
