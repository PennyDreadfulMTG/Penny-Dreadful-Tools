import asyncio
from typing import Any, Dict, List, Optional, Tuple, cast

import pytest
from dis_snek import Snake
from dis_snek.models.command import BaseCommand
from dis_snek.models.context import Context

from discordbot.bot import Bot
from discordbot.command import MtgMixin
from discordbot.commands import CardConverter
from magic.models import Card
from shared.container import Container


@pytest.fixture(scope='module')
def discordbot() -> Bot:
    bot = Bot()
    return bot

class ContextForTests(Context, MtgMixin):
    sent = False
    sent_args = False
    sent_file = False
    content: Optional[str] = None
    bot: Snake = None

    async def send(self, content: Optional[str], *args: Any, **kwargs: Any) -> None:  # pylint: disable=signature-differs
        self.sent = True
        self.sent_args = bool(args)
        self.sent_file = 'file' in kwargs.keys()
        self.content = content

    async def trigger_typing(self) -> None:
        ...

async def card(param: str) -> Card:
    ctx = ContextForTests()
    return cast(Card, await CardConverter.convert(ctx, param))


def get_params() -> List[Tuple]:
    async def params() -> List[Tuple]:
        return [
            ('art', {'card': 'Island'}, None),
            ('barbs', {}, None),
            ('echo', {'args': 'test string!'}, None),
            ('explain', {'thing': None}, None),
            ('explain', {'thing': 'bugs'}, None),
            ('flavor', {'card': 'Falling Star'}, 'No flavor text available'),  # No flavor
            ('flavor', {'card': 'Dwarven Pony'}, 'likes to eat meat'),  # Meaty flavor
            ('flavor', {'card': 'Gruesome Menagerie|grn'}, 'Variety is also the spice of death.'),  # Spicy flavor
            ('flavor', {'card': 'capital offense|UST'}, 'part basket case, all lowercase.'),  # Capital flavor
            ('flavor', {'card': 'Reliquary Tower|plg20'}, 'Archmage Vintra'),  # Long set code
            ('history', {'card': 'Necropotence'}, None),
            ('legal', {'card': 'Island'}, None),
            ('legal', {'card': 'Black Lotus'}, None),
            ('oracle', {'card': 'Dark Ritual'}, None),
            pytest.param('p1p1', {}, None, marks=pytest.mark.functional),
            ('patreon', {}, None),
            ('price', {'card': 'Gleemox'}, None),
            ('rotation', {}, None),
            pytest.param('rhinos', {}, None, marks=pytest.mark.functional),
            ('rulings', {'card': 'Worldknit'}, None),
            ('scry', {'query': 'f:pd'}, None),
            ('status', {}, None),
            ('time', {'args': 'AEST'}, None),
            ('tournament', {}, None),
            ('version', {}, None),
            ('whois', {'args': 'silasary'}, None),
            ('whois', {'args': 'kaet'}, None),
            ('whois', {'args': '<@154363842451734528>'}, None),
            ('whois', {'args': '<@!224755717767299072>'}, None),
        ]
    loop = asyncio.new_event_loop()
    return loop.run_until_complete(params())

@pytest.mark.functional
@pytest.mark.asyncio
@pytest.mark.parametrize('cmd, kwargs, expected_content', get_params())
async def test_command(discordbot: Snake, cmd: str, kwargs: Dict[str, Any], expected_content: str) -> None:
    command = find_command(discordbot, cmd)

    ctx = ContextForTests()
    ctx.bot = discordbot
    ctx.channel = Container({'id': '1'})
    ctx.channel.send = ctx.send
    ctx.channel.trigger_typing = ctx.trigger_typing
    ctx.message = Container()
    ctx.message.channel = ctx.channel
    ctx.author = Container()
    ctx.author.mention = '<@111111111111>'
    ctx.kwargs = kwargs
    ctx.args = []
    ctx.content_parameters = kwargs.get('args', '')
    await command(ctx, **kwargs)
    assert ctx.sent
    if expected_content is not None and ctx.content is not None:
        assert expected_content in ctx.content

def find_command(discordbot: Snake, cmd: str) -> BaseCommand:
    command = None
    for cmds in discordbot.interactions.values():
        if cmd in cmds:
            command = cmds[cmd]
            break
    else:
        command = discordbot.commands[cmd]
    return command
