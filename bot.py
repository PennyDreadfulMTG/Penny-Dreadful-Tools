import discord

import command
import configuration
import emoji
import oracle

class Bot:
    def __init__(self):
        self.legal_cards = []
        self.client = discord.Client()
        self.oracle = oracle.Oracle()

    def init(self):
        self.legal_cards = self.oracle.get_legal_cards()
        print('Legal cards: {num_legal_cards}'.format(num_legal_cards=len(self.legal_cards)))
        self.client.run(configuration.get('token'))

    async def on_ready(self):
        print('Logged in as {username} ({id})'.format(username=self.client.user.name, id=self.client.user.id))
        print('--------')

    async def on_message(self, message):
        # We do not want the bot to reply to itself.
        if message.author == self.client.user:
            return
        if message.content.startswith('!'):
            await self.respond_to_command(message)
        else:
            await self.respond_to_card_names(message)

    async def respond_to_card_names(self, message):
        await command.respond_to_card_names(message, self)

    async def respond_to_command(self, message):
        await command.handle_command(message, self)

    async def post_cards(self, cards, channel, additional_text='', verbose=False, legality=True, multirow=False):
        if len(cards) == 0:
            await self.client.send_message(channel, 'No matches.')
            return
        more_text = ''
        if len(cards) > 10 and not verbose and not multirow:
            more_text = ' and ' + str(len(cards) - 4) + ' more.'
            cards = cards[:4]
        if len(cards) == 1:
            card = cards[0]
            mana = emoji.replace_emoji(card.mana_cost, channel) or ''
            legal = command.legal_emoji(card, self.legal_cards, True)
            text = '{name} {mana_cost} — {type} — {legal}'.format(name=card.name, mana_cost=mana, type=card.type, legal=legal)
        else:
            if legality:
                text = ', '.join('{name} {legal}'.format(name=card.name, legal=command.legal_emoji(card, self.legal_cards)) for card in cards)
            else:
                text = ', '.join('{name} '.format(name=card.name) for card in cards)
            text += more_text
        images = []
        if (multirow):
            images.append(command.download_image(cards[:5], self.oracle) )
            images.append(command.download_image(cards[5:10], self.oracle) )
            images.append(command.download_image(cards[10:15], self.oracle) )
            
        else:
            images.append(command.download_image(cards, self.oracle) )
 
        text_written = False
        for image_file in images:
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
                if text_written:
                    await self.client.send_file(channel, image_file, content=None)
                else:
                    await self.client.send_file(channel, image_file, content=text)
                    text_written = True
