import asyncio
import re

import discord
from discord.member import Member
from discord.message import Message
from discord.reaction import Reaction
from discord.server import Server
from discord.state import Status

from discordbot import command
from magic import fetcher, multiverse, oracle, tournaments
from shared import configuration, dtutil
from shared.container import Container
from shared.pd_exception import InvalidDataException, TooFewItemsException


class Bot:
    def __init__(self) -> None:
        self.client = discord.Client()
        self.voice = None

    def init(self) -> None:
        multiverse.init()
        multiverse.update_bugged_cards()
        oracle.init()
        self.client.run(configuration.get('token'))

    async def on_ready(self) -> None:
        print('Logged in as {username} ({id})'.format(username=self.client.user.name, id=self.client.user.id))
        print('Connected to {0}'.format(', '.join([server.name for server in self.client.servers])))
        print('--------')

    async def on_message(self, message: Message) -> None:
        # We do not want the bot to reply to itself.
        if message.author == self.client.user:
            return
        if message.author.bot:
            return
        if message.content.startswith('!') and len(message.content.replace('!', '')) > 0:
            await command.handle_command(message, self.client)
        else:
            await command.respond_to_card_names(message, self.client)

    async def on_voice_state_update(self, before: Member, after: Member) -> None:
        # pylint: disable=unused-argument
        # If we're the only one left in a voice chat, leave the channel
        voice = after.server.voice_client
        if voice is None or not voice.is_connected():
            return
        if len(voice.channel.voice_members) == 1:
            await voice.disconnect()

    async def on_member_join(self, member: Member) -> None:
        print('{0} joined {1} ({2})'.format(member.mention, member.server.name, member.server.id))
        is_pd_server = member.server.id == '207281932214599682'
        # is_test_server = member.server.id == '226920619302715392'
        if is_pd_server: # or is_test_server:
            greeting = "Hey there {mention}, welcome to the Penny Dreadful community!  Be sure to set your nickname to your MTGO username, and check out <{url}> if you haven't already.".format(mention=member.mention, url=fetcher.decksite_url('/'))
            await self.client.send_message(member.server.default_channel, greeting)



BOT = Bot()

# Because of the way discord.py works I can't work out how to decorate instance methods.
# Thus we stub on_message and on_ready here and pass to Bot to do the real work.

@BOT.client.event
async def on_message(message: Message) -> None:
    await BOT.on_message(message)

@BOT.client.event
async def on_ready() -> None:
    await BOT.on_ready()

@BOT.client.event
async def on_voice_state_update(before: Member, after: Member) -> None:
    await BOT.on_voice_state_update(before, after)

@BOT.client.event
async def on_member_update(before: Member, after: Member) -> None:
    # streamers.
    roles = [r for r in before.server.roles if r.name == 'Currently Streaming']
    if roles:
        streaming_role = roles[0]
        if (not after.game or after.game.type == 0) and streaming_role in before.roles:
            print('{user} no longer streaming'.format(user=after.name))
            await BOT.client.remove_roles(after, streaming_role)
        if (after.game and after.game.type == 1) and not streaming_role in before.roles:
            print('{user} started streaming'.format(user=after.name))
            await BOT.client.add_roles(after, streaming_role)
    # Achivements
    if before.status == Status.offline and after.status == Status.online:
        data = None
        # Linked to PDM
        roles = [r for r in before.server.roles if r.name == 'Linked Magic Online']
        if roles and not roles[0] in before.roles:
            if data is None:
                data = fetcher.person_data(before.id)
            if data.get('id', None):
                await BOT.client.add_roles(after, roles[0])

@BOT.client.event
async def on_member_join(member: Member) -> None:
    await BOT.on_member_join(member)

@BOT.client.event
async def on_server_join(server: Server) -> None:
    await BOT.client.send_message(server.default_channel, "Hi, I'm mtgbot.  To look up cards, just mention them in square brackets. (eg `[Llanowar Elves] is better than [Elvish Mystic]`).")
    await BOT.client.send_message(server.default_channel, "By default, I display Penny Dreadful legality. If you don't want or need that, just type `!notpenny`.")

@BOT.client.event
async def on_reaction_add(reaction: Reaction, author: Member) -> None:
    if reaction.message.author == BOT.client.user:
        c = reaction.count
        if reaction.me:
            c = c - 1
        if c > 0 and not reaction.custom_emoji and reaction.emoji == '❎':
            await BOT.client.delete_message(reaction.message)
        elif c > 0 and 'Ambiguous name for ' in reaction.message.content and reaction.emoji in command.DISAMBIGUATION_EMOJIS_BY_NUMBER.values():
            await BOT.client.send_typing(reaction.message.channel)
            search = re.search(r'Ambiguous name for ([^\.]*)\. Suggestions: (.*)', reaction.message.content)
            if search:
                previous_command, suggestions = search.group(1, 2)
                card = re.findall(r':[^:]*?: ([^:]*) ', suggestions + ' ')[command.DISAMBIGUATION_NUMBERS_BY_EMOJI[reaction.emoji]-1]
                message = Container(content='!{c} {a}'.format(c=previous_command, a=card), channel=reaction.message.channel, author=author, reactions=[])
                await BOT.on_message(message)
                await BOT.client.delete_message(reaction.message)

async def background_task_spoiler_season() -> None:
    'Poll Scryfall for the latest 250 cards, and add them to our db if missing'
    await BOT.client.wait_until_ready()
    new_cards = fetcher.scryfall_cards()
    for c in new_cards['data']:
        await asyncio.sleep(5)
        try:
            oracle.valid_name(c['name'])
        except InvalidDataException:
            oracle.insert_scryfall_card(c, True)
            print('Imported {0} from Scryfall'.format(c['name']))
            return
        except TooFewItemsException:
            pass

async def background_task_tournaments() -> None:
    await BOT.client.wait_until_ready()
    tournament_channel_id = configuration.get('tournament_channel_id')
    if not tournament_channel_id:
        return
    channel = discord.Object(id=tournament_channel_id)
    while not BOT.client.is_closed:
        info = tournaments.next_tournament_info()
        diff = info['next_tournament_time_precise']
        if info['sponsor_name']:
            message = 'A {sponsor} sponsored tournament'.format(sponsor=info['sponsor_name'])
        else:
            message = 'A free tournament'
        embed = discord.Embed(title=info['next_tournament_name'], description=message)
        if diff <= 0:
            embed.add_field(name='Starting now', value='Check <#334220558159970304> for further annoucements')
        elif diff <= 14400:
            embed.add_field(name='Starting in:', value=dtutil.display_time(diff, 2))
            embed.add_field(name='Signup at:', value='https://gatherling.com')

        if diff <= 14400:
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
    asyncio.ensure_future(background_task_tournaments())
    BOT.init()
