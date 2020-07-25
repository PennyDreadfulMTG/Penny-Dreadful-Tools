import asyncio
from typing import Any, Dict, List, Tuple, cast, Optional

import discord
import pytest

from discordbot.bot import Bot
from discordbot.command import MtgContext
from discordbot.commands import CardConverter
from magic.models import Card
from shared.container import Container


@pytest.fixture(scope='module')
def discordbot() -> Bot:
    bot = Bot()
    return bot

class ContextForTests(MtgContext):
    def __init__(self, **attrs: Any) -> None:  # pylint: disable=super-init-not-called
        self.sent = False
        self.sent_args = False
        self.sent_file = False
        self.content: Optional[str] = None

    async def send(self, content: Optional[str], *args: Any, **kwargs: Any) -> None: # pylint: disable=signature-differs
        self.sent = True
        self.sent_args = bool(args)
        self.sent_file = 'file' in kwargs.keys()
        self.content = content

    def typing(self) -> 'ContextForTests':
        return self

    def __enter__(self) -> None:
        pass

    async def __aenter__(self) -> 'ContextForTests':
        return self

    def __exit__(self, exc_type, exc, tb):  # type: ignore
        pass

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore
        pass

async def card(param: str) -> Card:
    ctx = ContextForTests()
    return cast(Card, await CardConverter.convert(ctx, param))


def get_params() -> List[Tuple]:
    async def params() -> List[Tuple]:
        return [
            ('art', {'c': await card('Island')}, None),
            ('barbs', {}, None),
            ('echo', {'args': 'test string!'}, None),
            ('explain', {'thing': None}, None),
            ('explain', {'thing': 'bugs'}, None),
            ('flavor', {'c': await card('Falling Star')}, 'No flavor text available'), # No flavor
            ('flavor', {'c': await card('Dwarven Pony')}, 'likes to eat meat'),  # Meaty flavor
            ('flavor', {'c': await card('Gruesome Menagerie|grn')}, 'Variety is also the spice of death.'),  # Spicy flavor
            ('flavor', {'c': await card('capital offense|UST')}, 'part basket case, all lowercase.'),  # Capital flavor
            ('flavor', {'c': await card('Reliquary Tower|plgs')}, 'Archmage Vintra'),  # Long set code
            ('history', {'c': await card('Necropotence')}, None),
            ('legal', {'c': await card('Island')}, None),
            ('legal', {'c': await card('Black Lotus')}, None),
            ('oracle', {'c': await card('Dark Ritual')}, None),
            pytest.param('p1p1', {}, None, marks=pytest.mark.functional),
            ('patreon', {}, None),
            ('price', {'c': await card('Gleemox')}, None),
            ('rotation', {}, None),
            pytest.param('rhinos', {}, None, marks=pytest.mark.functional),
            ('rulings', {'c': await card('Worldknit')}, None),
            ('search', {'args': 'f:pd'}, None),
            ('status', {}, None),
            ('time', {'args': 'AEST'}, None),
            ('tournament', {}, None),
            ('version', {}, None),
            ('whois', {'args': 'silasary'}, None),
            ('whois', {'args': 'kaet'}, None),
            ('whois', {'args': '<@154363842451734528>'}, None),
            ('whois', {'args': '<@!224755717767299072>'}, None)
        ]
    loop = asyncio.new_event_loop()
    return loop.run_until_complete(params())

@pytest.mark.asyncio
@pytest.mark.parametrize('cmd, kwargs, expected_content', get_params())
async def test_command(discordbot: Bot, cmd: str, kwargs: Dict[str, Any], expected_content: str) -> None: # pylint: disable=redefined-outer-name
    command: discord.ext.commands.Command = discordbot.all_commands[cmd]
    ctx = ContextForTests()
    ctx.bot = discordbot
    ctx.message = Container()
    ctx.message.channel = Container({'id': '1'})
    ctx.message.channel.typing = ctx.typing
    ctx.message.channel.send = ctx.send
    ctx.author = Container()
    ctx.author.mention = '<@111111111111>'
    await command.callback(ctx, **kwargs)
    assert ctx.sent
    if expected_content is not None and ctx.content is not None:
        assert expected_content in ctx.content
