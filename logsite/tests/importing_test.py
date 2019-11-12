import os

from .. import importing
from ..data.match import Match


def import_log(match_id: int) -> Match:
    fname = '{path}/{filename}'.format(path=os.path.dirname(__file__), filename='{0}.txt'.format(match_id))
    with open(fname) as fhandle:
        lines = fhandle.readlines()
        return importing.import_log(lines, match_id)

def test_import_league() -> None:
    import_log(201109942)

def test_import_tourney() -> None:
    local = import_log(201088400)
    assert local.is_tournament
    assert local.tournament is not None

def test_import_switcheroo() -> None:
    local = import_log(198379247)
    assert local.has_unexpected_third_game
