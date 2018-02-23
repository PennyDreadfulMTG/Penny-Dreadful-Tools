import asyncio
import types

from discordbot import bot, command
from magic import fetcher_internal


# Mock up assertions within the discord client.
# I love that Python lets us just ruin 3rd-party libraries like this.
def generate_fakebot():
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
    fakebot = bot.Bot()
    fakebot.client.send_message = fake_send_message
    fakebot.client.send_file = fake_send_file
    fakebot.client.send_typing = fake_send_typing
    return fakebot

def generate_fakechannel():
    fakechannel = types.new_class('Channel')
    fakechannel.is_private = True
    fakechannel.calls = 0
    fakechannel.id = 0
    return fakechannel

def test_commands():
    fakebot = generate_fakebot()

    loop = asyncio.get_event_loop()
    for cmd in dir(command.Commands):
        if cmd.startswith('_'):
            continue
        if cmd in ['restartbot', 'updateprices', 'clearimagecache', 'bug']:
            continue

        channel = generate_fakechannel()
        calls = channel.calls

        message = types.new_class('Message')
        message.content = "!{0} args".format(cmd)
        message.channel = channel

        if cmd == 'time':
            message.content = '!time Melbourne'

        message.author = types.new_class('User')
        message.author.mention = "@nobody"
        message.author.voice = types.new_class('VoiceState')
        message.author.voice.voice_channel = None

        print("Calling {0}".format(message.content))
        loop.run_until_complete(command.handle_command(message, fakebot))
        assert channel.calls > calls
        calls = channel.calls

    loop.close()
