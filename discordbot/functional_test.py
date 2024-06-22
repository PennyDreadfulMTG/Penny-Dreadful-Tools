import random
from typing import Any

import pytest
from _pytest.mark.structures import ParameterSet
from interactions import Client
from interactions.models import BaseCommand, BaseContext, Guild

from discordbot.bot import Bot
from discordbot.command import MtgMixin
from shared.container import Container

pytest.skip('These need to be rewritten', allow_module_level=True)


@pytest.fixture(scope='module')
def discordbot() -> Bot:
    bot = Bot()
    bot.cache.guild_cache[207281932214599682] = Guild(client=bot, id=207281932214599682, name='PDM', owner_id=154363842451734528, preferred_locale='en-US')
    return bot


class ContextForTests(BaseContext, MtgMixin):
    sent = False
    sent_args = False
    sent_file = False
    content: str | None = None
    content_parameters: str
    id = random.randint(111111111111111111, 999999999999999999)

    async def send(self, content: str | None = None, *args: Any, **kwargs: Any) -> None:
        self.sent = True
        self.sent_args = bool(args)
        self.sent_file = 'file' in kwargs.keys()
        self.sent_embed = 'embed' in kwargs.keys()
        self.content = content

    async def trigger_typing(self) -> None: ...

    async def defer(self) -> None: ...


def get_params() -> list[ParameterSet | tuple[str, dict[str, Any], str | None, str | None]]:
    return [
        ('art', {'card': 'Island'}, None, None),
        ('barbs', {}, None, None),
        # ('echo', {'args': 'test string!'}, None, None),
        ('explain', {'thing': None}, None, None),
        ('explain', {'thing': 'bugs'}, None, None),
        ('flavor', {'card': 'Falling Star'}, 'No flavor text available', None),  # No flavor
        ('flavor', {'card': 'Dwarven Pony'}, 'likes to eat meat', None),  # Meaty flavor
        ('flavor', {'card': 'Gruesome Menagerie|grn'}, 'Variety is also the spice of death.', None),  # Spicy flavor
        ('flavor', {'card': 'capital offense|UST'}, 'part basket case, all lowercase.', None),  # Capital flavor
        ('flavor', {'card': 'Reliquary Tower|plg20'}, 'Archmage Vintra', None),  # Long set code
        ('history', {'card': 'Necropotence'}, None, None),
        ('legal', {'card': 'Island'}, None, None),
        ('legal', {'card': 'Black Lotus'}, None, None),
        ('oracle', {'card': 'Dark Ritual'}, None, None),
        pytest.param('p1p1', {}, None, None, marks=pytest.mark.functional),
        ('patreon', {}, None, None),
        ('price', {'card': 'Gleemox'}, None, None),
        ('rotation', {}, None, None),
        pytest.param('rhinos', {}, None, None, marks=pytest.mark.functional),
        ('rulings', {'card': 'Worldknit'}, None, None),
        ('scry', {'query': 'f:pd'}, None, None),
        ('status', {}, None, None),
        ('time', {'place': 'AEST'}, None, None),
        ('tournament', {}, None, None),
        ('version', {}, None, None),
        # ('whois', {'args': 'silasary'}, None, 'whois'),
        # ('whois', {'args': 'kaet'}, None, 'whois'),
        # ('whois', {'args': '<@154363842451734528>'}, None, 'whois'),
        # ('whois', {'args': '<@!224755717767299072>'}, None, 'whois'),
    ]


@pytest.mark.functional
@pytest.mark.asyncio
@pytest.mark.parametrize('cmd, kwargs, expected_content, function_name', get_params())
async def test_command(discordbot: Client, cmd: str, kwargs: dict[str, Any], expected_content: str, function_name: str) -> None:
    command = find_command(discordbot, cmd, function_name)
    assert command is not None
    print(f'command: {command}')

    ctx = ContextForTests()
    ctx._client = discordbot
    ctx.guild_id = 207281932214599682
    ctx.channel = Container({'id': '1'})
    ctx.channel.guild = ctx.guild
    ctx.channel.send = ctx.send
    ctx.channel.trigger_typing = ctx.trigger_typing
    ctx.message = Container()
    ctx.message.channel = ctx.channel
    ctx.author = Container(id=2)
    ctx.author.mention = '<@111111111111>'
    ctx.kwargs = kwargs
    ctx.args = []
    ctx.content_parameters = kwargs.get('args', '')
    await command(ctx, **kwargs)
    assert ctx.sent
    if expected_content is not None and ctx.content is not None:
        assert expected_content in ctx.content


def find_command(discordbot: Client, cmd: str, function_name: str | None = None) -> BaseCommand | None:
    for command in discordbot.application_commands:
        if isinstance(command.name, str):
            name = command.name
        else:
            name = command.name.default

        if cmd == name:
            print(f'found command {command} - {command.callback}')
            return command
    else:
        p_command = discordbot.prefixed_commands.get(cmd, None)
        if p_command is not None:
            print(f'found command {p_command} - {p_command.callback}')
        return p_command
