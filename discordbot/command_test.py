import datetime
from unittest.mock import AsyncMock, Mock

import pytest

from discordbot import command
from discordbot.commands import resources


def test_roughly_matches() -> None:
    assert command.roughly_matches('hello', 'hello')
    assert command.roughly_matches('signup', 'Sign Up')
    assert not command.roughly_matches('elephant', 'Tuba')
    assert command.roughly_matches('jmeka', 'j_meka')
    assert command.roughly_matches('modo bugs', 'modo-bugs')

def test_results_from_queries() -> None:
    result = command.results_from_queries(['bolt'])[0][0]
    assert result.has_match()
    assert not result.is_ambiguous()
    assert result.get_best_match() == 'Lightning Bolt'
    result = command.results_from_queries(['Far/Away'])[0][0]
    assert result.has_match()
    assert not result.is_ambiguous()
    assert result.get_best_match() == 'Far // Away'
    result = command.results_from_queries(['Jötun Grunt'])[0][0]
    assert result.has_match()
    assert not result.is_ambiguous()
    assert result.get_best_match() == 'Jötun Grunt'
    result = command.results_from_queries(['Jotun Grunt'])[0][0]
    assert result.has_match()
    assert not result.is_ambiguous()
    assert result.get_best_match() == 'Jötun Grunt'
    result = command.results_from_queries(['Ready / Willing'])[0][0]
    assert result.has_match()
    assert not result.is_ambiguous()
    assert result.get_best_match() == 'Ready // Willing'
    result = command.results_from_queries(['Fire // Ice'])[0][0]
    assert result.has_match()
    assert not result.is_ambiguous()
    assert result.get_best_match() == 'Fire // Ice'
    result = command.results_from_queries(['Upheaval'])[0][0]
    assert result.has_match()
    assert not result.is_ambiguous()
    assert result.get_best_match() == 'Upheaval'
    result = command.results_from_queries(['Llanowar Elves|7ED'])[0][0]
    assert result.has_match()
    assert not result.is_ambiguous()
    assert result.get_best_match() == 'Llanowar Elves'
    result = command.results_from_queries(['Wasteland'])[0][0]
    assert result.has_match()
    assert not result.is_ambiguous()
    assert result.get_best_match() == 'Wasteland'


def test_do_not_choke_on_unicode() -> None:
    s = '①②④⑧⇅⊕█↑▪🐞🚫🏆⏩⏪︎📰💻▾'
    # As a whole…
    result = command.results_from_queries([s])[0][0]
    assert not result.has_match()
    # …and for each char individually.
    for result, _, _ in command.results_from_queries(list(s)):
        assert not result.has_match()

def test_resources_matching_in_url() -> None:
    results = resources.resources_resources('github')
    assert results['https://github.com/PennyDreadfulMTG/Penny-Dreadful-Tools/'] == 'Penny Dreadful Tools'

    results = resources.resources_resources('starcitygames')
    assert results['https://old.starcitygames.com/article/33860_Penny-Dreadful.html'] == 'Mrs. Mulligan SCG'

def test_escape_underscores() -> None:
    r = command.escape_underscores('simple_test')
    assert r == 'simple\\_test'
    r = command.escape_underscores('<simple_test>')
    assert r == '<simple_test>'
    r = command.escape_underscores('people gimmick_: <https://pennydreadfulmagic.com/people/gimmick_/>')
    assert r == 'people gimmick\\_: <https://pennydreadfulmagic.com/people/gimmick_/>'
    r = command.escape_underscores(':white_check_mark:')
    assert r == ':white_check_mark:'
    r = command.escape_underscores('Adamaro, First to Desire :white_check_mark:')
    assert r == 'Adamaro, First to Desire :white_check_mark:'

def test_no_warning_for_recent_card_information(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.datetime(2026, 8, 21, tzinfo=datetime.UTC)
    monkeypatch.setattr(command.dtutil, 'now', lambda: now)
    monkeypatch.setattr(command.database, 'last_updated', lambda: now - command.MAX_CARD_INFORMATION_AGE)

    assert command.stale_card_information_warning() == ''

def test_warning_for_stale_card_information(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.datetime(2026, 8, 21, tzinfo=datetime.UTC)
    monkeypatch.setattr(command.dtutil, 'now', lambda: now)
    monkeypatch.setattr(command.database, 'last_updated', lambda: now - datetime.timedelta(days=29))

    assert command.stale_card_information_warning() == '\nWARNING: card information is 4 weeks old'

@pytest.mark.asyncio
async def test_no_matches_includes_card_information_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    message = Mock()
    message.add_reaction = AsyncMock()
    channel = Mock()
    channel.send = AsyncMock(return_value=message)
    monkeypatch.setattr(command, 'stale_card_information_warning', lambda: '\nWARNING: card information is 4 weeks old')

    await command.post_nothing(channel)

    channel.send.assert_awaited_once_with(file=None, content='No matches.\nWARNING: card information is 4 weeks old')
