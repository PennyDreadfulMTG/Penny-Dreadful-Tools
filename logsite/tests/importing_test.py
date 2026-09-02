import os

import pytest

from logsite import APP

from .. import importing
from ..data.match import Match


def import_log(match_id: int) -> Match:
    fname = '{path}/{filename}'.format(path=os.path.dirname(__file__), filename=f'{match_id}.txt')
    with open(fname) as fhandle:
        lines = fhandle.readlines()
        return importing.import_log(lines, match_id)

@pytest.mark.functional
def test_import_league() -> None:
    with APP.app_context():
        import_log(201109942)

@pytest.mark.functional
def test_import_tourney() -> None:
    with APP.app_context():
        local = import_log(201088400)
        assert local.is_tournament
        assert local.tournament is not None

@pytest.mark.functional
def test_import_switcheroo() -> None:
    with APP.app_context():
        local = import_log(198379247)
        assert local.has_unexpected_third_game

@pytest.mark.functional
def test_host_is_first_player_in_log() -> None:
    # The host is the player who appears first in the log header (index 0).
    # set(players) would destroy this ordering; dict.fromkeys preserves it.
    with APP.app_context():
        local = import_log(201109942)
        assert local.host().name == 'subrosian_z'
