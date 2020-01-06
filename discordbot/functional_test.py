import asyncio

import discord
import pytest

from discordbot.bot import Bot
from discordbot.command import MtgContext
from discordbot.commands import Card, CardConverter
from shared.container import Container


@pytest.fixture(scope='module')
def discordbot() -> Bot:
    bot = Bot()
    bot.init()
    return bot

class TestContext(MtgContext):
    def __init__(self, **attrs) -> None:
        self.sent = False

    async def send(self, *args, **kwargs) -> None:
        self.sent = True

    def typing(self) -> 'TestContext':
        return self

    def __enter__(self) -> None:
        pass

    def __exit__(self, _, __, ___):
        pass

async def card(param: str) -> Card:
    ctx = TestContext()
    return await CardConverter.convert(ctx, param)


def get_params():
    async def params():
        return [
            ('art', {'c': await card('Island')}),
            ('barbs', {}),
            # ('downtimes', {}),
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
            ('p1p1', {}),
            ('patreon', {}),
            ('price', {'c': await card('Gleemox')}),
            ('rotation', {}),
            # ('rulings', {'c': await card('Worldknit')}),


        ]
    loop = asyncio.new_event_loop()
    return loop.run_until_complete(params())

@pytest.mark.asyncio
@pytest.mark.parametrize('cmd, kwargs', get_params())
async def test_command(discordbot: Bot, cmd: str, kwargs) -> None:
    command: discord.ext.commands.Command = discordbot.all_commands[cmd]
    ctx = TestContext()
    ctx.bot = discordbot
    ctx.message = Container()
    ctx.message.channel = Container({'id': '1'})
    await command.callback(ctx, **kwargs)
    assert ctx.sent
