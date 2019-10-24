import types
from typing import Any

import discord

from shared import fetcher_internal


# Mock up assertions within the discord client.
# I love that Python lets us just ruin 3rd-party libraries like this.
def generate_fakebot() -> discord.Client:
    async def fake_send_message(channel, text):
        print('Responding with "{0}"'.format(text))
        channel.calls += 1
        assert channel is not None
        assert text is not None and text != ''
    async def fake_send_file(channel, image_file, content=None):
        print('Uploading "{0}", with additional text "{1}"'.format(image_file, content))
        channel.calls += 1
        assert channel is not None
        assert image_file is not None and fetcher_internal.acceptable_file(image_file)
        assert content != ''
    async def fake_send_typing(channel):
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

# @pytest.mark.functional
# @pytest.mark.xfail(reason='API changes.  Needs full rewrite')
# def test_commands() -> None:
#     fakebot = generate_fakebot()

#     loop = asyncio.get_event_loop()
#     for cmd in dir(command.Commands):
#         if cmd.startswith('_'):
#             continue
#         if cmd in ['restartbot', 'updateprices', 'clearimagecache', 'bug', 'gbug']:
#             continue

#         channel = generate_fakechannel()
#         calls = channel.calls # type: ignore

#         message = types.new_class('Message')
#         message.content = '!{0} args'.format(cmd) # type: ignore
#         message.channel = channel # type: ignore

#         if cmd == 'time':
#             message.content = '!time Melbourne' # type: ignore

#         message.author = types.new_class('User') # type: ignore
#         message.author.mention = '@nobody' # type: ignore
#         message.author.voice = types.new_class('VoiceState') # type: ignore
#         message.author.voice.voice_channel = None # type: ignore

#         print('Calling {0}'.format(message.content)) # type: ignore
#         loop.run_until_complete(command.handle_command(message, fakebot))
#         assert channel.calls > calls # type: ignore
#         calls = channel.calls # type: ignore

#     loop.close()
