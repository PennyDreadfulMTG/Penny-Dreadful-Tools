from magic import seasons
from shared.pd_exception import DoesNotExistException


def test_seasons_enum_uptodate() -> None:
    """If this is failing, go append new set codes to seasons.SEASONS.
       This needs to be done every few months.

       This test is purely for futureproofing, and failing it does not mean anything is currently broken"""
    if seasons.next_rotation_ex().code in ['???', None]:
        return
    assert seasons.next_rotation_ex().code in seasons.SEASONS

def test_season_id() -> None:
    assert seasons.season_id(1) == 1
    found = False
    try:
        seasons.season_id(999)
    except DoesNotExistException:
        found = True
    assert found
    found = False
    try:
        assert seasons.season_id('ISD')
    except DoesNotExistException:
        found = True
    assert found
    assert seasons.season_id('HOU') == 5
    assert seasons.season_id('hou') == 5
    assert seasons.season_id('ALL') == 'all'
    assert seasons.season_id('all') == 'all'

def test_season_code() -> None:
    assert seasons.season_code(1) == 'EMN'
    found = False
    try:
        seasons.season_code(999)
    except DoesNotExistException:
        found = True
    assert found
    found = False
    try:
        assert seasons.season_code('ISD')
    except DoesNotExistException:
        found = True
    assert found
    assert seasons.season_code('HOU') == 'HOU'
    assert seasons.season_code('hou') == 'HOU'
    assert seasons.season_code('ALL') == 'ALL'
    assert seasons.season_code('all') == 'ALL'

def test_season_name() -> None:
    assert seasons.season_name(1) == 'Season 1'
    found = False
    try:
        seasons.season_name(999)
    except DoesNotExistException:
        found = True
    assert found
    found = False
    try:
        assert seasons.season_name('ISD')
    except DoesNotExistException:
        found = True
    assert found
    assert seasons.season_name('EMN') == 'Season 1'
    assert seasons.season_name('emn') == 'Season 1'
    assert seasons.season_name('HOU') == 'Season 5'
    assert seasons.season_name('hou') == 'Season 5'
    assert seasons.season_name('ALL') == 'All Time'
    assert seasons.season_name('all') == 'All Time'
    assert seasons.season_name(0) == 'All Time'
