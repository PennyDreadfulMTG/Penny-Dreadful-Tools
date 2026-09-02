import datetime
import glob
import importlib
import inspect
import os
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from interactions.models.internal.application_commands import SlashCommand

from discordbot import command, commands
from discordbot.commands import CardConverter, resources
from magic.models import Card, Printing


def test_all_slash_commands_have_descriptions() -> None:
    commands_dir = os.path.join(os.path.dirname(__file__), 'commands')
    paths = glob.glob(os.path.join(commands_dir, '*.py'))
    missing = []
    for path in sorted(paths):
        name = os.path.basename(path)[:-3]
        if name.startswith('_') or name.endswith('_test'):
            continue
        module = importlib.import_module(f'discordbot.commands.{name}')
        for _cls_name, cls in inspect.getmembers(module, inspect.isclass):
            for _attr_name, obj in inspect.getmembers_static(cls):
                if isinstance(obj, SlashCommand) and str(obj.description) == 'No Description Set':
                    missing.append(f'{name}.{obj.name}')
    assert missing == [], f'Slash commands missing descriptions: {missing}'


def test_command_setup_does_not_load_test_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    bot = Mock()
    monkeypatch.setattr(commands.glob, 'glob', Mock(return_value=['/commands/spoiler.py', '/commands/spoiler_test.py', '/commands/__init__.py']))
    monkeypatch.setattr(commands.path, 'isfile', Mock(return_value=True))

    commands.setup(bot)

    bot.load_extension.assert_called_once_with('.spoiler', 'discordbot.commands')


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

def test_copy_with_mode_preserves_official_alternate_name_and_printing(monkeypatch: pytest.MonkeyPatch) -> None:
    card = Card({'name': 'Agent Venom', 'flavor_names': 'Rhilex the Accursed'})
    printing = Printing({'set_code': 'om1', 'system_id': 'd62cf4f8-36a2-4d9f-9d52-53ea18a52760'})
    monkeypatch.setattr(command.oracle, 'preferred_printing_for_alternate_name', lambda _card, _name: printing)

    result = command.copy_with_mode(card, '', requested_name='Rhilex the Accursed')

    assert result.display_name == 'Rhilex the Accursed'
    assert result.preferred_printing == 'om1'
    assert result.preferred_printing_system_id == 'd62cf4f8-36a2-4d9f-9d52-53ea18a52760'
    assert command.card_name_for_display(result) == 'Rhilex the Accursed (Agent Venom)'

def test_copy_with_mode_keeps_canonical_requests_on_the_default_printing() -> None:
    card = Card({'name': 'Zilortha, Strength Incarnate', 'flavor_names': 'Godzilla, King of the Monsters'})

    result = command.copy_with_mode(card, '', requested_name='Zilortha, Strength Incarnate')

    assert result.get('display_name') is None
    assert result.preferred_printing is None
    assert result.get('preferred_printing_system_id') is None

def test_copy_with_mode_keeps_explicit_set_syntax(monkeypatch: pytest.MonkeyPatch) -> None:
    card = Card({'name': 'Zilortha, Strength Incarnate', 'flavor_names': 'Godzilla, King of the Monsters'})
    monkeypatch.setattr(
        command.oracle,
        'preferred_printing_for_alternate_name',
        lambda *_args: pytest.fail('An explicit set must take precedence'),
    )

    result = command.copy_with_mode(card, '', preferred_printing='iko', requested_name='Godzilla, King of the Monsters|iko')

    assert result.display_name == 'Godzilla, King of the Monsters'
    assert result.preferred_printing == 'iko'
    assert result.get('preferred_printing_system_id') is None

def test_copy_with_mode_does_not_display_search_only_alias() -> None:
    card = Card({'name': 'Dark Confidant'})

    result = command.copy_with_mode(card, '', requested_name='bob')

    assert result.get('display_name') is None
    assert command.card_name_for_display(result) == 'Dark Confidant'

@pytest.mark.asyncio
async def test_autocomplete_displays_official_alternate_name(monkeypatch: pytest.MonkeyPatch) -> None:
    result = Mock()
    result.get_all_matches.return_value = ['Agent Venom']
    monkeypatch.setattr(command, 'searcher', lambda: Mock(search=Mock(return_value=result)))
    monkeypatch.setattr(command.oracle, 'load_card', lambda _name: Card({'name': 'Agent Venom', 'flavor_names': 'Rhilex the Accursed'}))
    ctx = Mock()
    ctx.kwargs = {'card': 'rhil'}
    ctx.send = AsyncMock()

    await command.autocomplete_card(ctx)

    ctx.send.assert_awaited_once_with(choices=[{'name': 'Rhilex the Accursed — Agent Venom', 'value': 'Rhilex the Accursed'}])


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

    results = resources.resources_resources('magic online guide')
    assert results['https://www.mtgo.com/getting-started/getting-started-home'] == 'Magic Online guide'

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
    monkeypatch.setattr(command.database, 'stale_card_information_age', lambda: None)

    assert command.stale_card_information_warning() == ''

def test_warning_for_stale_card_information(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(command.database, 'stale_card_information_age', lambda: datetime.timedelta(days=29))

    assert command.stale_card_information_warning() == '\nWARNING: card information is 4 weeks old'

@pytest.mark.asyncio
async def test_card_converter_uses_buttons_for_ambiguous_names(monkeypatch: pytest.MonkeyPatch) -> None:
    matches = ['Brainstone', 'Brainstorm', 'Harmonized Trio', 'Brain Freeze', 'Brain Maggot', 'Brain Pry']
    shown_matches = matches[:5]
    result = Mock()
    result.has_match.return_value = True
    result.is_ambiguous.return_value = True
    result.get_ambiguous_matches.return_value = matches
    selected_card = Mock()
    monkeypatch.setattr(command, 'results_from_queries', lambda _: [(result, '', None)])
    cards_from_names = Mock(return_value=[selected_card])
    monkeypatch.setattr(command, 'cards_from_names_with_mode', cards_from_names)

    ctx = Mock()
    ctx.author.id = 123
    ctx.author.mention = '<@123>'
    ctx.invoke_target = 'history'
    message = Mock()
    message.edit = AsyncMock()
    ctx.send = AsyncMock(return_value=message)
    pressed_ctx = Mock()
    pressed_ctx.author.id = 123
    pressed_ctx.edit_origin = AsyncMock()

    async def choose_second(message_arg: object, components: list[Any], check: Any, timeout: int) -> object:
        assert message_arg == message
        assert timeout == 60
        matching_event = Mock()
        matching_event.ctx = pressed_ctx
        other_event = Mock()
        other_event.ctx.author.id = 456
        assert check(matching_event)
        assert not check(other_event)
        pressed_ctx.custom_id = components[1].custom_id
        return matching_event

    ctx.client.wait_for_component = AsyncMock(side_effect=choose_second)

    converted = await CardConverter.convert(ctx, 'brain')

    assert converted == selected_card
    sent_components = ctx.send.await_args.kwargs['components']
    assert len(sent_components) == 1
    assert [button.label for button in sent_components[0]] == shown_matches
    assert all(button.emoji is None for button in sent_components[0])
    cards_from_names.assert_called_once_with(['Brainstorm'], '', None, 'brain')
    pressed_ctx.edit_origin.assert_awaited_once_with(content='<@123>: Selected **Brainstorm**.', components=[])
    event = ctx.client.wait_for_component.await_args
    assert event.kwargs['components'][1].custom_id is not None

@pytest.mark.asyncio
async def test_no_matches_includes_card_information_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    message = Mock()
    message.add_reaction = AsyncMock()
    channel = Mock()
    channel.send = AsyncMock(return_value=message)
    monkeypatch.setattr(command, 'stale_card_information_warning', lambda: '\nWARNING: card information is 4 weeks old')

    await command.post_nothing(channel)

    channel.send.assert_awaited_once_with(file=None, content='No matches.\nWARNING: card information is 4 weeks old')
