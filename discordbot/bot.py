import asyncio
import datetime
import re
from typing import List

import discord
from discord.channel import Channel
from discord.member import Member
from discord.message import Message

from discordbot import command, emoji
from magic import fetcher, image_fetcher, multiverse, oracle, tournaments
from magic.card import Card
from shared import configuration, dtutil
from shared.container import Container
from shared.pd_exception import InvalidDataException
from shared.whoosh_search import WhooshSearcher


class Bot:
    def __init__(self) -> None:
        self.client = discord.Client()
        self.voice = None
        self.searcher: WhooshSearcher = None

    def init(self) -> None:
        multiverse.init()
        multiverse.update_bugged_cards()
        oracle.init()
        self.searcher = WhooshSearcher()
        self.client.run(configuration.get('token'))

    async def on_ready(self) -> None:
        print('Logged in as {username} ({id})'.format(username=self.client.user.name, id=self.client.user.id))
        print('Connected to {0}'.format(', '.join([server.name for server in self.client.servers])))
        print('--------')

    async def on_message(self, message: Message):
        # We do not want the bot to reply to itself.
        if message.author == self.client.user:
            return
        if message.author.bot:
            return
        if message.content.startswith('!') and len(message.content.replace('!', '')) > 0:
            await self.respond_to_command(message)
        else:
            await self.respond_to_card_names(message)

    async def on_voice_state_update(self, before: Member, after: Member) -> None:
        # pylint: disable=unused-argument
        # If we're the only one left in a voice chat, leave the channel
        voice = after.server.voice_client
        if voice is None or not voice.is_connected():
            return
        if len(voice.channel.voice_members) == 1:
            await voice.disconnect()

    async def respond_to_card_names(self, message: Message) -> None:
        await command.respond_to_card_names(message, self)

    async def respond_to_command(self, message: Message) -> None:
        await command.handle_command(message, self)

    async def post_cards(
            self,
            cards: List[Card],
            channel: Channel,
            replying_to: Member = None,
            additional_text: str = ''
    ) -> None:
        await self.client.send_typing(channel)
        if len(cards) == 0:
            await self.post_no_cards(channel, replying_to)
            return
        disable_emoji = channel.id in configuration.get('not_pd').split(',')
        cards = command.uniqify_cards(cards)
        if len(cards) > command.MAX_CARDS_SHOWN:
            cards = cards[:command.DEFAULT_CARDS_SHOWN]
        if len(cards) == 1:
            text = self.single_card_text(cards[0], disable_emoji)
        else:
            text = ', '.join('{name} {legal} {price}'.format(name=card.name, legal=((emoji.legal_emoji(card)) if not disable_emoji else ''), price=((fetcher.card_price_string(card, True)) if card.get('mode', None) == '$' else '')) for card in cards)
        if len(cards) > command.MAX_CARDS_SHOWN:
            image_file = None
        else:
            image_file = image_fetcher.download_image(cards)
        if image_file is None:
            text += '\n\n'
            if len(cards) == 1:
                text += emoji.replace_emoji(cards[0].text, self.client)
            else:
                text += 'No image available.'
        text += additional_text
        if image_file is None:
            await self.client.send_message(channel, text)
        else:
            await self.send_image_with_retry(channel, image_file, text)

    async def post_no_cards(self, channel, replying_to: Member) -> None:
        if replying_to is not None:
            text = '{author}: No matches.'.format(author=replying_to.mention)
        else:
            text = 'No matches.'
        message = await self.client.send_message(channel, text)
        await self.client.add_reaction(message, '❎')
        return


    async def send_image_with_retry(self, channel, image_file, text='') -> None:
        message = await self.client.send_file(channel, image_file, content=text)
        if message and message.attachments and message.attachments[0]['size'] == 0:
            print('Message size is zero so resending')
            await self.client.delete_message(message)
            await self.client.send_file(channel, image_file, content=text)

    async def on_member_join(self, member) -> None:
        print('{0} joined {1} ({2})'.format(member.mention, member.server.name, member.server.id))
        is_pd_server = member.server.id == "207281932214599682"
        # is_test_server = member.server.id == "226920619302715392"
        if is_pd_server: # or is_test_server:
            greeting = "Hey there {mention}, welcome to the Penny Dreadful community!  Be sure to set your nickname to your MTGO username, and check out <{url}> and <http://pdmtgo.com> if you haven't already.".format(mention=member.mention, url=fetcher.decksite_url('/'))
            await self.client.send_message(member.server.default_channel, greeting)

    def single_card_text(self, card, disable_emoji) -> str:
        mana = emoji.replace_emoji(''.join(card.mana_cost or []), self.client)
        legal = ' — ' + emoji.legal_emoji(card, True)
        if disable_emoji:
            legal = ''
        if card.get('mode', None) == '$':
            text = '{name} {legal} — {price}'.format(name=card.name, price=fetcher.card_price_string(card), legal=legal)
        else:
            text = '{name} {mana} — {type}{legal}'.format(name=card.name, mana=mana, type=card.type, legal=legal)
        if card.bugs:
            for bug in card.bugs:
                text += '\n:beetle:{rank} bug: {bug}'.format(bug=bug['description'], rank=bug['classification'])
                if bug['last_confirmed'] < (dtutil.now() - datetime.timedelta(days=60)):
                    time_since_confirmed = (dtutil.now() - bug['last_confirmed']).seconds
                    text += ' (Last confirmed {time} ago.)'.format(time=dtutil.display_time(time_since_confirmed, 1))
        return text


BOT = Bot()

# Because of the way discord.py works I can't work out how to decorate instance methods.
# Thus we stub on_message and on_ready here and pass to Bot to do the real work.

@BOT.client.event
async def on_message(message) -> None:
    await BOT.on_message(message)

@BOT.client.event
async def on_ready() -> None:
    await BOT.on_ready()

@BOT.client.event
async def on_voice_state_update(before, after) -> None:
    await BOT.on_voice_state_update(before, after)

@BOT.client.event
async def on_member_update(before, after) -> None:
    streaming_role = [r for r in before.server.roles if r.name == "Currently Streaming"]
    if not streaming_role:
        return
    streaming_role = streaming_role[0]
    if (not after.game or after.game.type == 0) and streaming_role in before.roles:
        print('{user} no longer streaming'.format(user=after.name))
        await BOT.client.remove_roles(after, streaming_role)
    if (after.game and after.game.type == 1) and not streaming_role in before.roles:
        print('{user} started streaming'.format(user=after.name))
        await BOT.client.add_roles(after, streaming_role)

@BOT.client.event
async def on_member_join(member) -> None:
    await BOT.on_member_join(member)

@BOT.client.event
async def on_server_join(server) -> None:
    await BOT.client.send_message(server.default_channel, "Hi, I'm mtgbot.  To look up cards, just mention them in square brackets. (eg `[Llanowar Elves] is better than [Elvish Mystic]`).")
    await BOT.client.send_message(server.default_channel, "By default, I display Penny Dreadful legality. If you don't want or need that, just type `!notpenny`.")

@BOT.client.event
async def on_reaction_add(reaction, author) -> None:
    if reaction.message.author == BOT.client.user:
        c = reaction.count
        if reaction.me:
            c = c - 1
        if c > 0 and not reaction.custom_emoji and reaction.emoji == "❎":
            await BOT.client.delete_message(reaction.message)
        elif c > 0 and "Ambiguous name for " in reaction.message.content and reaction.emoji in command.DISAMBIGUATION_EMOJIS_BY_NUMBER.values():
            await BOT.client.send_typing(reaction.message.channel)
            previous_command, suggestions = re.search(r"Ambiguous name for ([^\.]*)\. Suggestions: (.*)", reaction.message.content).group(1, 2)
            card = re.findall(r":[^:]*?: ([^:]*) ", suggestions + " ")[command.DISAMBIGUATION_NUMBERS_BY_EMOJI[reaction.emoji]-1]
            message = Container(content="!{c} {a}".format(c=previous_command, a=card), channel=reaction.message.channel, author=author, reactions=[])
            await BOT.on_message(message)
            await BOT.client.delete_message(reaction.message)

async def background_task_spoiler_season() -> None:
    "Poll Scryfall for the latest 250 cards, and add them to our db if missing"
    await BOT.client.wait_until_ready()
    new_cards = fetcher.scryfall_cards()
    for c in new_cards['data']:
        try:
            oracle.valid_name(c['name'])
        except InvalidDataException:
            oracle.insert_scryfall_card(c)
            print('Imported {0} from Scryfall'.format(c['name']))

async def background_task_tournaments() -> None:
    await BOT.client.wait_until_ready()
    tournament_channel_id = configuration.get('tournament_channel_id')
    if not tournament_channel_id:
        return
    channel = discord.Object(id=tournament_channel_id)
    while not BOT.client.is_closed:
        info = tournaments.next_tournament_info()
        diff = info['next_tournament_time_precise']
        if diff <= 0:
            message = 'Tournament starting!'
        elif diff <= 14400:
            message = 'Starting: {0}.'.format(dtutil.display_time(diff, 2))

        if diff <= 14400:
            embed = discord.Embed(title=info['next_tournament_name'], description=message)
            embed.set_image(url=fetcher.decksite_url('/favicon-152.png'))
            # See #2809.
            # pylint: disable=no-value-for-parameter,unexpected-keyword-arg
            await BOT.client.send_message(channel, embed=embed)

        if diff <= 300:
            # Five minutes, final warning.  Sleep until the tournament has started.
            timer = 301
        elif diff <= 1800:
            # Half an hour. Sleep until 5 minute warning.
            timer = diff - 300
        elif diff <= 3600:
            # One hour.  Sleep until half-hour warning.
            timer = diff - 1800
        else:
            # Wait until four hours before tournament.
            timer = 3600 + diff % 3600
            if diff > 3600 * 6:
                # The timer can afford to get off-balance by doing other background work.
                await background_task_spoiler_season()
                multiverse.update_bugged_cards()

        if timer < 300:
            timer = 300
        print('diff={0}, timer={1}'.format(diff, timer))
        await asyncio.sleep(timer)

def init() -> None:
    asyncio.ensure_future(background_task_spoiler_season())
    asyncio.ensure_future(background_task_tournaments())
    BOT.init()
