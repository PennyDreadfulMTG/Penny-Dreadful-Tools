import types
from typing import Any, Optional

import discord
from discord.channel import TextChannel

from shared import fetch_tools


# Mock up assertions within the discord client.
# I love that Python lets us just ruin 3rd-party libraries like this.
def generate_fakebot() -> discord.Client:
    async def fake_send_message(channel: TextChannel, text: str) -> None:
        print('Responding with "{0}"'.format(text))
        channel.calls += 1
        assert channel is not None
        assert text is not None and text != ''
    async def fake_send_file(channel: TextChannel, image_file: str, content: Optional[str]) -> None:
        print('Uploading "{0}", with additional text "{1}"'.format(image_file, content))
        channel.calls += 1
        assert channel is not None
        assert image_file is not None and fetch_tools.acceptable_file(image_file)
        assert content != ''
    async def fake_send_typing(channel: TextChannel) -> None:
        assert channel is not None
    fakebot = discord.Client()
    fakebot.send_message = fake_send_message
    fakebot.send_file = fake_send_file
    fakebot.send_typing = fake_send_typing
    return fakebot

def generate_fakechannel() -> Any:
    fakechannel = types.new_class('Channel')
    fakechannel.is_private = True # type: ignore
    fakechannel.calls = 0 # type: ignore
    fakechannel.id = 0 # type: ignore
    return fakechannel
