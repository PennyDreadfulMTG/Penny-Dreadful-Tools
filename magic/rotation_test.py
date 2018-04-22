from magic import rotation
from shared.pd_exception import DoesNotExistException


def test_determine_season_id():
    assert rotation.determine_season_id(1) == 1
    found = False
    try:
        rotation.determine_season_id(999)
    except DoesNotExistException:
        found =  True
    assert found
    found = False
    try:
        assert rotation.determine_season_id('ISD')
    except DoesNotExistException:
        found = True
    assert found
    assert rotation.determine_season_id('HOU') == 5
    assert rotation.determine_season_id('hou') == 5
    assert rotation.determine_season_id('ALL') == 'all'
    assert rotation.determine_season_id('all') == 'all'
