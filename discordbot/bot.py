import asyncio
import re
import sys
from typing import Any, List, Optional

import discord
from discord import Guild, Role, VoiceState
from discord.activity import Streaming
from discord.errors import Forbidden, NotFound
from discord.member import Member
from discord.message import Message
from discord.reaction import Reaction
from discord.state import Status
from github.GithubException import GithubException

from discordbot import command
from magic import fetcher, multiverse, oracle, tournaments
from shared import configuration, dtutil, redis, repo
from shared.container import Container
from shared.pd_exception import InvalidDataException, TooFewItemsException


class Bot(discord.Client):
    def __init__(self) -> None:
        super().__init__()
        self.voice = None

    def init(self) -> None:
        multiverse.init()
        multiverse.update_bugged_cards()
        oracle.init()
        self.run(configuration.get('token'))

    async def on_ready(self) -> None:
        print('Logged in as {username} ({id})'.format(username=self.user.name, id=self.user.id))
        print('Connected to {0}'.format(', '.join([guild.name for guild in self.guilds])))
        print('--------')

    async def on_message(self, message: Message) -> None:
        # We do not want the bot to reply to itself.
        if message.author == self.user:
            return
        if message.author.bot:
            return
        if message.content.startswith('!') and len(message.content.replace('!', '')) > 0:
            await command.handle_command(message, self)
        else:
            await command.respond_to_card_names(message, self)

    async def on_voice_state_update(self, member: Member, before: VoiceState, after: VoiceState) -> None:
        # pylint: disable=unused-argument
        # If we're the only one left in a voice chat, leave the channel
        if getattr(after.channel, 'guild', None) is None:
            return
        voice = after.channel.guild.voice_client
        if voice is None or not voice.is_connected():
            return
        if len(voice.channel.voice_members) == 1:
            await voice.disconnect()

    async def on_member_join(self, member: Member) -> None:
        print('{0} joined {1} ({2})'.format(member.mention, member.guild.name, member.guild.id))

        # is_test_server = member.guild.id == 226920619302715392
        if is_pd_server(member.guild): # or is_test_server:
            greeting = "Hey there {mention}, welcome to the Penny Dreadful community!  Be sure to set your nickname to your MTGO username, and check out <{url}> if you haven't already.".format(mention=member.mention, url=fetcher.decksite_url('/'))
            chan = member.guild.get_channel(207281932214599682) #general (Yes, the guild ID is the same as the ID of it's first channel.  It's not a typo)
            print(f'Greeting in {chan}')
            await chan.send(greeting)

    async def on_member_update(self, before: Member, after: Member) -> None:
        if before.bot:
            return
        # streamers.
        streaming_role = await get_role(before.guild, 'Currently Streaming')
        if streaming_role:
            if not isinstance(after.activity, Streaming) and streaming_role in before.roles:
                print('{user} no longer streaming'.format(user=after.name))
                await after.remove_roles(streaming_role)
            if isinstance(after.activity, Streaming) and not streaming_role in before.roles:
                print('{user} started streaming'.format(user=after.name))
                await after.add_roles(streaming_role)
        # Achievements
        if before.status == Status.offline and after.status == Status.online:
            data = None
            # Linked to PDM
            role = await get_role(before.guild, 'Linked Magic Online')
            if role is not None and not role in before.roles:
                if data is None:
                    data = await fetcher.person_data_async(before.id)
                if data.get('id', None):
                    await after.add_roles(role)

            key = f'discordbot:achivements:players:{before.id}'
            if not redis.get_bool(key) and not data:
                data = await fetcher.person_data_async(before.id)
                redis.store(key, True, ex=14400)

            # Trophies
            if is_pd_server(before.guild) and data is not None and data.get('achievements', None) is not None:
                expected: List[Role] = []
                remove: List[Role] = []
                for name, count in data['achievements'].items():
                    if int(count) > 0:
                        trophy = f'🏆 {name}'
                        role = await get_role(before.guild, trophy, create=True)
                        expected.append(role)
                for role in before.roles:
                    if role in expected:
                        expected.remove(role)
                    elif '🏆' in role.name:
                        remove.append(role)
                await before.remove_roles(*remove)
                await before.add_roles(*expected)


    async def on_guild_join(self, server: Guild) -> None:
        for channel in server.text_channels:
            try:
                await channel.send("Hi, I'm mtgbot.  To look up cards, just mention them in square brackets. (eg `[Llanowar Elves] is better than [Elvish Mystic]`).")
                await channel.send("By default, I display Penny Dreadful legality. If you don't want or need that, just type `!notpenny`.")
                return
            except Forbidden:
                pass

    async def on_reaction_add(self, reaction: Reaction, author: Member) -> None:
        if reaction.message.author == self.user:
            c = reaction.count
            if reaction.me:
                c = c - 1
            if c > 0 and not reaction.custom_emoji and reaction.emoji == '❎':
                try:
                    await reaction.message.delete()
                except NotFound: # Someone beat us to it?
                    pass
            elif c > 0 and 'Ambiguous name for ' in reaction.message.content and reaction.emoji in command.DISAMBIGUATION_EMOJIS_BY_NUMBER.values():
                async with reaction.message.channel.typing():
                    search = re.search(r'Ambiguous name for ([^\.]*)\. Suggestions: (.*)', reaction.message.content)
                    if search:
                        previous_command, suggestions = search.group(1, 2)
                        card = re.findall(r':[^:]*?: ([^:]*) ', suggestions + ' ')[command.DISAMBIGUATION_NUMBERS_BY_EMOJI[reaction.emoji]-1]
                        message = Container(content='!{c} {a}'.format(c=previous_command, a=card), channel=reaction.message.channel, author=author, reactions=[])
                        await self.on_message(message)
                        await reaction.message.delete()

    async def on_error(self, event_method: str, *args: Any, **kwargs: Any) -> None:
        await super().on_error(event_method, args, kwargs)
        (_, exception, __) = sys.exc_info()
        try:
            content = [arg.content for arg in args if hasattr(arg, 'content')] # The default string representation of a Message does not include the message content.
            repo.create_issue(f'Bot error {event_method}\n{args}\n{kwargs}\n{content}', 'discord user', 'discordbot', 'PennyDreadfulMTG/perf-reports', exception=exception)
        except GithubException as e:
            print('Github error', e, file=sys.stderr)

    async def background_task_spoiler_season(self) -> None:
        'Poll Scryfall for the latest 250 cards, and add them to our db if missing'
        try:
            await self.wait_until_ready()
            new_cards = await fetcher.scryfall_cards_async()
            for c in new_cards['data']:
                if c['layout'] == 'double_faced_token':
                    continue # These cause issues for little benefit.  Let's just ignore them for now.
                try:
                    oracle.valid_name(c['name'])
                    await asyncio.sleep(1)
                except InvalidDataException:
                    oracle.insert_scryfall_card(c, True)
                    print('Imported {0} from Scryfall'.format(c['name']))
                    await asyncio.sleep(5)
                except TooFewItemsException:
                    pass
        except Exception: # pylint: disable=broad-except
            await self.on_error('background_task_spoiler_season')


    async def background_task_tournaments(self) -> None:
        try:
            await self.wait_until_ready()
            tournament_channel_id = configuration.get_int('tournament_reminders_channel_id')
            if not tournament_channel_id:
                print('tournament channel is not configured')
                return
            channel = self.get_channel(tournament_channel_id)
            while self.is_ready:
                info = tournaments.next_tournament_info()
                diff = info['next_tournament_time_precise']
                if info['sponsor_name']:
                    message = 'A {sponsor} sponsored tournament'.format(sponsor=info['sponsor_name'])
                else:
                    message = 'A free tournament'
                embed = discord.Embed(title=info['next_tournament_name'], description=message)
                if diff <= 1:
                    embed.add_field(name='Starting now', value='Check <#334220558159970304> for further annoucements')
                elif diff <= 14400:
                    embed.add_field(name='Starting in:', value=dtutil.display_time(diff, 2))
                    embed.add_field(name='Pre-register now:', value='https://gatherling.com')

                if diff <= 14400:
                    embed.set_image(url=fetcher.decksite_url('/favicon-152.png'))
                    # See #2809.
                    # pylint: disable=no-value-for-parameter,unexpected-keyword-arg
                    await channel.send(embed=embed)

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
                        await self.background_task_spoiler_season()
                        multiverse.update_bugged_cards()

                if timer < 300:
                    timer = 300
                print('diff={0}, timer={1}'.format(diff, timer))
                await asyncio.sleep(timer)
            print('naturally stopping tournament reminders')
        except Exception: # pylint: disable=broad-except
            await self.on_error('background_task_tournaments')


def init() -> None:
    client = Bot()
    asyncio.ensure_future(client.background_task_tournaments(), loop=client.loop)
    asyncio.ensure_future(client.background_task_spoiler_season(), loop=client.loop)
    client.init()

def is_pd_server(guild: Guild) -> bool:
    return guild.id == 207281932214599682 # or guild.id == 226920619302715392

async def get_role(guild: Guild, rolename: str, create: bool = False) -> Optional[Role]:
    for r in guild.roles:
        if r.name == rolename:
            return r
    if create:
        return await guild.create_role(name=rolename)
    return None
