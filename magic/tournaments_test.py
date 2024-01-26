import datetime

import freezegun
import pytest

from magic import seasons, tournaments
from magic.models import Competition, Deck
from shared import dtutil

COMPETITIONS = {
    'pd500': Competition({'name': 'Penny Dreadful 500 (Season 99)'}),
    'kick_off': Competition({'name': 'Penny Dreadful Kick Off (Season 99)'}),
    'normal': Competition({'name': 'Penny Dreadful Monday 99.99'}),
}

@pytest.mark.xfail(reason='The code this is testing will only ever rename the current season')
def test_get_all_next_tournament_dates() -> None:
    with freezegun.freeze_time('2021-02-01'):
        seasons.rotation_info().recalculate()
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

def test_pd500_prizes() -> None:
    prizes = tournaments.pd500_prizes()
    assert len(prizes) == 5
    assert prizes[0]['finish'] == '1st'
    assert prizes[0]['prize'] == 130
    assert prizes[4]['finish'] == '9th–16th'
    assert prizes[4]['prize'] == 10

def test_kick_off_prizes() -> None:
    prizes = tournaments.kick_off_prizes()
    assert len(prizes) == 7
    assert prizes[2]['finish'] == '3rd–4th'
    assert prizes[2]['prize'] == 10
    assert prizes[5]['finish'] == '17th–24th'
    assert prizes[5]['prize'] == 2

def test_normal_prizes() -> None:
    prizes = tournaments.normal_prizes()
    assert len(prizes) == 4
    assert prizes[0]['finish'] == '1st'
    assert prizes[0]['prize'] == 4
    assert prizes[3]['finish'] == '5th–8th'
    assert prizes[3]['prize'] == 1

def test_prizes_by_finish() -> None:
    prizes = tournaments.prizes_by_finish(COMPETITIONS['pd500'])
    assert len(prizes) == 16
    assert prizes[0]['finish'] == '1st'
    assert prizes[0]['prize'] == 130
    assert prizes[10]['finish'] == '11th'
    assert prizes[10]['prize'] == 10
    prizes = tournaments.prizes_by_finish(COMPETITIONS['kick_off'])
    assert len(prizes) == 32
    assert prizes[2]['finish'] == '3rd'
    assert prizes[2]['prize'] == 10
    assert prizes[18]['finish'] == '19th'
    assert prizes[18]['prize'] == 2
    prizes = tournaments.prizes_by_finish(COMPETITIONS['normal'])
    assert len(prizes) == 8
    assert prizes[0]['finish'] == '1st'
    assert prizes[0]['prize'] == 4
    assert prizes[6]['finish'] == '7th'
    assert prizes[6]['prize'] == 1

def test_prize() -> None:
    assert 10 == tournaments.prize(COMPETITIONS['pd500'], Deck({'finish': 12}))
    assert 3 == tournaments.prize(COMPETITIONS['kick_off'], Deck({'finish': 15}))
    assert 3 == tournaments.prize(COMPETITIONS['normal'], Deck({'finish': 2}))

def test_prize_by_finish() -> None:
    assert 10 == tournaments.prize_by_finish(COMPETITIONS['pd500'], 12)
    assert 3 == tournaments.prize_by_finish(COMPETITIONS['kick_off'], 15)
    assert 3 == tournaments.prize_by_finish(COMPETITIONS['normal'], 2)

def test_pd500_prize() -> None:
    assert 10 == tournaments.pd500_prize(12)

def test_kick_off_prize() -> None:
    assert 3 == tournaments.kick_off_prize(15)

def test_normal_prize() -> None:
    assert 3 == tournaments.normal_prize(2)
    assert 0 == tournaments.normal_prize(15)

def test_display_prizes() -> None:
    ps: tournaments.Prizes = [
        {'finish': '1st', 'prize': 4},
        {'finish': '2nd', 'prize': 3},
        {'finish': '3rd', 'prize': 2},
        {'finish': '4th', 'prize': 2},
        {'finish': '5th', 'prize': 1},
        {'finish': '6th', 'prize': 1},
        {'finish': '7th', 'prize': 1},
        {'finish': '8th', 'prize': 1},
    ]
    r = tournaments.display_prizes(ps)
    assert r == [
        {'finish': '1st', 'prize': 4},
        {'finish': '2nd', 'prize': 3},
        {'finish': '3rd–4th', 'prize': 2},
        {'finish': '5th–8th', 'prize': 1},
    ]

def test_all_series_info() -> None:
    si = tournaments.all_series_info()
    dates = tournaments.get_all_next_tournament_dates(dtutil.now(dtutil.GATHERLING_TZ))
    assert len(si) == len(dates)
