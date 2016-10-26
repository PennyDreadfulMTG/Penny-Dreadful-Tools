import discord

import command
import emoji
from magic import configuration, oracle


class Bot:
    def __init__(self):
        self.legal_cards = []
        self.client = discord.Client()
        self.voice = None

    def init(self):
        self.legal_cards = oracle.get_legal_cards()
        print('Legal cards: {num_legal_cards}'.format(num_legal_cards=len(self.legal_cards)))
        self.client.run(configuration.get('token'))

    async def on_ready(self):
        print('Logged in as {username} ({id})'.format(username=self.client.user.name, id=self.client.user.id))
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
            mana = emoji.replace_emoji(card.mana_cost, channel) or ''
            legal = command.legal_emoji(card, self.legal_cards, True)
            text = '{name} {mana_cost} — {type} — {legal}'.format(name=card.name, mana_cost=mana, type=card.type, legal=legal)
        else:
            text = ', '.join('{name} {legal}'.format(name=card.name, legal=command.legal_emoji(card, self.legal_cards)) for card in cards)
            text += more_text
        if len(cards) > 10:
            image_file = None
        else:
            image_file = command.download_image(cards)
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
