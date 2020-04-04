from magic import rotation
from shared.pd_exception import DoesNotExistException


def test_seasons_enum_uptodate() -> None:
    """If this is failing, go append new set codes to rotation.SEASONS.
       This needs to be done every few months.

       This test is purely for futureproofing, and failing it does not mean anything is currently broken"""
    if rotation.next_rotation_ex().code in ['???', None]:
        return
    assert rotation.next_rotation_ex().code in rotation.SEASONS

def test_season_id() -> None:
    assert rotation.season_id(1) == 1
    found = False
    try:
        rotation.season_id(999)
    except DoesNotExistException:
        found = True
    assert found
    found = False
    try:
        assert rotation.season_id('ISD')
    except DoesNotExistException:
        found = True
    assert found
    assert rotation.season_id('HOU') == 5
    assert rotation.season_id('hou') == 5
    assert rotation.season_id('ALL') == 'all'
    assert rotation.season_id('all') == 'all'

def test_season_code() -> None:
    assert rotation.season_code(1) == 'EMN'
    found = False
    try:
        rotation.season_code(999)
    except DoesNotExistException:
        found = True
    assert found
    found = False
    try:
        assert rotation.season_code('ISD')
    except DoesNotExistException:
        found = True
    assert found
    assert rotation.season_code('HOU') == 'HOU'
    assert rotation.season_code('hou') == 'HOU'
    assert rotation.season_code('ALL') == 'ALL'
    assert rotation.season_code('all') == 'ALL'

def test_season_name() -> None:
    assert rotation.season_name(1) == 'Season 1'
    found = False
    try:
        rotation.season_name(999)
    except DoesNotExistException:
        found = True
    assert found
    found = False
    try:
        assert rotation.season_name('ISD')
    except DoesNotExistException:
        found = True
    assert found
    assert rotation.season_name('EMN') == 'Season 1'
    assert rotation.season_name('emn') == 'Season 1'
    assert rotation.season_name('HOU') == 'Season 5'
    assert rotation.season_name('hou') == 'Season 5'
    assert rotation.season_name('ALL') == 'All Time'
    assert rotation.season_name('all') == 'All Time'
    assert rotation.season_name(0) == 'All Time'
