import asyncio
from typing import Any, Dict, List, Tuple, cast

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

    async def send(self, *args: Any, **kwargs: Any) -> None: # pylint: disable=signature-differs
        self.sent = True
        self.sent_args = bool(args)
        self.sent_file = 'file' in kwargs.keys()

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
            ('art', {'c': await card('Island')}),
            ('barbs', {}),
            ('echo', {'args': 'test string!'}),
            ('explain', {'thing': None}),
            ('explain', {'thing': 'bugs'}),
            ('flavor', {'c': await card('Island')}), # No flavor
            ('flavor', {'c': await card('Horned Turtle')}),  # Tasty Flavor
            ('flavor', {'c': await card('Gruesome Menagerie|RNA')}),  # Spicy Flavor
            ('history', {'c': await card('Necropotence')}),
            ('legal', {'c': await card('Island')}),
            ('legal', {'c': await card('Black Lotus')}),
            ('oracle', {'c': await card('Dark Ritual')}),
            pytest.param('p1p1', {}, marks=pytest.mark.functional),
            ('patreon', {}),
            ('price', {'c': await card('Gleemox')}),
            ('rotation', {}),
            pytest.param('rhinos', {}, marks=pytest.mark.functional),
            ('rulings', {'c': await card('Worldknit')}),
            ('search', {'args': 'f:pd'}),
            ('status', {}),
            ('time', {'args': 'AEST'}),
            ('tournament', {}),
            ('version', {}),
            ('whois', {'args': 'silasary'}),
            ('whois', {'args': 'kaet'}),
            ('whois', {'args': '<@154363842451734528>'}),
            ('whois', {'args': '<@!224755717767299072>'})
        ]
    loop = asyncio.new_event_loop()
    return loop.run_until_complete(params())

@pytest.mark.asyncio
@pytest.mark.parametrize('cmd, kwargs', get_params())
async def test_command(discordbot: Bot, cmd: str, kwargs: Dict[str, Any]) -> None: # pylint: disable=redefined-outer-name
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
