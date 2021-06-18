import datetime
from typing import Dict, List

import pytest

from decksite.data.competition import Competition
from magic import tournaments
from magic.models import Deck
from shared import dtutil

COMPETITIONS = {
    'pd500': Competition({'name': 'Penny Dreadful 500 (Season 99)'}),
    'kick_off': Competition({'name': 'Penny Dreadful Kick Off (Season 99)'}),
    'normal': Competition({'name': 'Penny Dreadful Monday 99.99'}),
}

# pylint: disable=invalid-name
@pytest.mark.xfail(reason='The code this is testing will only ever rename the current season')
def test_get_all_next_tournament_dates() -> None:
    just_before_s19_kick_off = datetime.datetime(2021, 2, 19).astimezone(tz=dtutil.WOTC_TZ)
    just_after_s19_kick_off = datetime.datetime(2021, 2, 21).astimezone(tz=dtutil.WOTC_TZ)
    info = tournaments.get_all_next_tournament_dates(just_before_s19_kick_off)
    assert info[0][1] == 'Penny Dreadful FNM'
    assert info[1][1] == 'Season Kick Off'
    info = tournaments.get_all_next_tournament_dates(just_after_s19_kick_off)
    assert info[-1][1] == 'Penny Dreadful Thursdays'

def test_is_pd500() -> None:
    assert tournaments.is_pd500(COMPETITIONS['pd500'])
    assert not tournaments.is_pd500(COMPETITIONS['kick_off'])
    assert not tournaments.is_pd500(COMPETITIONS['normal'])

def test_is_kick_off() -> None:
    assert not tournaments.is_kick_off(COMPETITIONS['pd500'])
    assert tournaments.is_kick_off(COMPETITIONS['kick_off'])
    assert not tournaments.is_kick_off(COMPETITIONS['normal'])

def inspect_pd500_prizes(prizes: tournaments.Prizes) -> None:
    assert len(prizes) == 16
    assert prizes[0]['finish'] == '1st'
    assert prizes[0]['prize'] == 130
    assert prizes[10]['finish'] == '11th'
    assert prizes[10]['prize'] == 10

def inspect_kick_off_prizes(prizes: tournaments.Prizes) -> None:
    assert len(prizes) == 32
    assert prizes[2]['finish'] == '3rd'
    assert prizes[2]['prize'] == 15
    assert prizes[18]['finish'] == '19th'
    assert prizes[18]['prize'] == 2

def inspect_normal_prizes(prizes: tournaments.Prizes) -> None:
    assert len(prizes) == 8
    assert prizes[0]['finish'] == '1st'
    assert prizes[0]['prize'] == 4
    assert prizes[6]['finish'] == '7th'
    assert prizes[6]['prize'] == 1

def test_pd500_prizes() -> None:
    prizes = tournaments.pd500_prizes()
    inspect_pd500_prizes(prizes)

def test_kick_off_prizes() -> None:
    prizes = tournaments.kick_off_prizes()
    inspect_kick_off_prizes(prizes)

def test_normal_prizes() -> None:
    prizes = tournaments.normal_prizes()
    inspect_normal_prizes(prizes)

def test_prizes_by_finish() -> None:
    prizes = tournaments.prizes_by_finish(COMPETITIONS['pd500'])
    inspect_pd500_prizes(prizes)
    prizes = tournaments.prizes_by_finish(COMPETITIONS['kick_off'])
    inspect_kick_off_prizes(prizes)
    prizes = tournaments.prizes_by_finish(COMPETITIONS['normal'])
    inspect_normal_prizes(prizes)

def test_prize() -> None:
    assert 10 == tournaments.prize(COMPETITIONS['pd500'], Deck({'finish': 12}))
    assert 5 == tournaments.prize(COMPETITIONS['kick_off'], Deck({'finish': 15}))
    assert 3 == tournaments.prize(COMPETITIONS['normal'], Deck({'finish': 2}))

def test_prize_by_finish() -> None:
    assert 10 == tournaments.prize_by_finish(COMPETITIONS['pd500'], 12)
    assert 5 == tournaments.prize_by_finish(COMPETITIONS['kick_off'], 15)
    assert 3 == tournaments.prize_by_finish(COMPETITIONS['normal'], 2)

def test_pd500_prize() -> None:
    assert 10 == tournaments.pd500_prize(12)

def test_kick_off_prize() -> None:
    assert 5 == tournaments.kick_off_prize(15)

def test_normal_prize() -> None:
    assert 3 == tournaments.normal_prize(2)
    assert 0 == tournaments.normal_prize(15)
