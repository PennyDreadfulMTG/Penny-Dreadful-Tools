import discord

from discordbot import command, emoji
from magic import image_fetcher
from shared import configuration, dtutil

class Bot:
    def __init__(self):
        self.client = discord.Client()
        self.voice = None

    def init(self):
        self.client.run(configuration.get('token'))

    async def on_ready(self):
        print('Logged in as {username} ({id})'.format(username=self.client.user.name, id=self.client.user.id))
        print('Connected to {0}'.format(', '.join([server.name for server in self.client.servers])))
        print('--------')

    async def on_message(self, message):
        # We do not want the bot to reply to itself.
        if message.author == self.client.user:
            return
        if message.content.startswith('!') and len(message.content.replace('!', '')) > 0:
            await self.respond_to_command(message)
        else:
            await self.respond_to_card_names(message)

    async def on_voice_state_update(self, before, after):
        #pylint: disable=unused-argument
        # If we're the only one left in a voice chat, leave the channel
        voice = after.server.voice_client
        if voice is None or not voice.is_connected():
            return
        if len(voice.channel.voice_members) == 1:
            await voice.disconnect()

    async def respond_to_card_names(self, message):
        await command.respond_to_card_names(message, self)

    async def respond_to_command(self, message):
        await command.handle_command(message, self)

    async def post_cards(self, cards, channel, replying_to=None, additional_text=''):
        await self.client.send_typing(channel)
        if len(cards) == 0:
            if replying_to is not None:
                text = '{author}: No matches.'.format(author=replying_to.mention)
            else:
                text = 'No matches.'
            await self.client.send_message(channel, text)
            return
        cards = command.uniqify_cards(cards)
        more_text = ''
        if len(cards) > 10:
            more_text = ' and ' + str(len(cards) - 4) + ' more.'
            cards = cards[:4]
        if len(cards) == 1:
            card = cards[0]
            mana = emoji.replace_emoji(''.join(card.mana_cost or []), channel)
            legal = emoji.legal_emoji(card, True)
            text = '{name} {mana} — {type} — {legal}'.format(name=card.name, mana=mana, type=card.type, legal=legal)
            if card.bug_desc is not None:
                text += '\n:beetle:{rank} bug: {bug}'.format(bug=card.bug_desc, rank=card.bug_class)
                now_ts = dtutil.dt2ts(dtutil.now())
                if card.bug_last_confirmed < now_ts - 60 * 60 * 24 * 60:
                    text += ' (Last confirmed {time} ago.)'.format(time=dtutil.display_time(now_ts - card.bug_last_confirmed, 1))
        else:
            text = ', '.join('{name} {legal}'.format(name=card.name, legal=emoji.legal_emoji(card)) for card in cards)
            text += more_text
        if len(cards) > 10:
            image_file = None
        else:
            image_file = image_fetcher.download_image(cards)
        if image_file is None:
            text += '\n\n'
            if len(cards) == 1:
                text += emoji.replace_emoji(cards[0].text, channel)
            else:
                text += 'No image available.'
        text += '\n' + additional_text
        if image_file is None:
            await self.client.send_message(channel, text)
        else:
            message = await self.client.send_file(channel, image_file, content=text)
            if message and message.attachments and message.attachments[0]['size'] == 0:
                print('Message size is zero so resending')
                await self.client.delete_message(message)
                await self.client.send_file(channel, image_file, content=text)

BOT = Bot()

# Because of the way discord.py works I can't work out how to decorate instance methods.
# Thus we stub on_message and on_ready here and pass to Bot to do the real work.

@BOT.client.event
async def on_message(message):
    await BOT.on_message(message)

@BOT.client.event
async def on_ready():
    await BOT.on_ready()

@BOT.client.event
async def on_voice_state_update(before, after):
    await BOT.on_voice_state_update(before, after)

def init():
    BOT.init()
