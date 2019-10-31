import asyncio
import datetime
import re
import sys
from typing import Any, Callable, Dict, List, Optional

import discord
from discord import Guild, Member, Role, VoiceState
from discord.activity import Streaming
from discord.errors import Forbidden, NotFound
from discord.ext import commands
from discord.message import Message
from discord.reaction import Reaction
from discord.state import Status
from github.GithubException import GithubException

import discordbot.commands
from discordbot import command
from magic import fetcher, multiverse, oracle, rotation, tournaments
from magic.card_description import CardDescription
from magic.models import Card
from shared import configuration, dtutil
from shared import fetcher_internal as internal
from shared import perf, redis, repo
from shared.container import Container
from shared.pd_exception import InvalidDataException

TASKS = []

def background_task(func: Callable) -> Callable:
    async def wrapper(self: discord.Client) -> None:
        try:
            await self.wait_until_ready()
            await func(self)
        except Exception: # pylint: disable=broad-except
            await self.on_error(func.__name__)
    TASKS.append(wrapper)
    return wrapper


class Bot(commands.Bot):
    def __init__(self, **kwargs: Any) -> None:
        self.launch_time = perf.start()
        super().__init__(command_prefix='!', help_command=commands.DefaultHelpCommand(dm_help=True), **kwargs)
        self.voice = None
        self.achievement_cache: Dict[str, Dict[str, str]] = {}
        for task in TASKS:
            asyncio.ensure_future(task(self), loop=self.loop)

    def init(self) -> None:
        multiverse.init()
        multiverse.update_bugged_cards()
        oracle.init()
        discordbot.commands.setup(self)
        self.run(configuration.get('token'))

    async def on_ready(self) -> None:
        print('Logged in as {username} ({id})'.format(username=self.user.name, id=self.user.id))
        print('Connected to {0}'.format(', '.join([guild.name for guild in self.guilds])))
        print('--------')
        perf.check(self.launch_time, 'slow_bot_start', '', 'discordbot')

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
        role = await get_role(before.guild, 'Linked Magic Online')
        if role and before.status == Status.offline and after.status == Status.online:
            data = None
            # Linked to PDM
            if role is not None and not role in before.roles:
                if data is None:
                    data = await fetcher.person_data_async(before.id)
                if data.get('id', None):
                    await after.add_roles(role)

            key = f'discordbot:achievements:players:{before.id}'
            if is_pd_server(before.guild) and not redis.get_bool(key) and not data:
                data = await fetcher.person_data_async(before.id)
                redis.store(key, True, ex=14400)

            # Trophies
            if is_pd_server(before.guild) and data is not None and data.get('achievements', None) is not None:
                expected: List[Role] = []
                remove: List[Role] = []
                async def achievement_name(key: str) -> str:
                    name = self.achievement_cache.get(key, None)
                    if name is None:
                        self.achievement_cache.update(await fetcher.achievement_cache_async())
                        name = self.achievement_cache[key]
                    return f'🏆 {name["title"]}'

                for name, count in data['achievements'].items():
                    if int(count) > 0:
                        trophy = await achievement_name(name)
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
                        # pylint: disable=protected-access
                        message = Container(content='!{c} {a}'.format(c=previous_command, a=card), channel=reaction.message.channel, author=author, reactions=[], _state=reaction.message._state)
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

    @background_task
    async def background_task_spoiler_season(self) -> None:
        'Poll Scryfall for the latest 250 cards, and add them to our db if missing'
        latest_cards = await fetcher.scryfall_cards_async()
        cards_not_currently_in_db: List[CardDescription] = []
        for c in latest_cards['data']:
            name = multiverse.name_from_card_description(c)
            try:
                oracle.valid_name(name)
            except InvalidDataException:
                print(f'Planning to add {name} to database in background_task_spoiler_season.')
                cards_not_currently_in_db.append(c)
        if len(cards_not_currently_in_db) > 0:
            oracle.add_cards_and_update(cards_not_currently_in_db)

    @background_task
    async def background_task_tournaments(self) -> None:
        tournament_channel_id = configuration.get_int('tournament_reminders_channel_id')
        if not tournament_channel_id:
            print('tournament channel is not configured')
            return
        channel = self.get_channel(tournament_channel_id)
        if channel is None:
            print(f'ERROR: could not find tournament_channel_id {tournament_channel_id}')
            return
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
                # Sleep for one hour plus enough to have a whole number of hours left.
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

    @background_task
    async def background_task_league_end(self) -> None:
        tournament_channel_id = configuration.get_int('tournament_reminders_channel_id')
        if not tournament_channel_id:
            print('tournament channel is not configured')
            return
        channel = self.get_channel(tournament_channel_id)
        while self.is_ready:
            try:
                league = await internal.fetch_json_async(fetcher.decksite_url('/api/league'))
            except internal.FetchException as e:
                print("Couldn't reach decksite or decode league json with error message(s) {0}".format(
                    '; '.join(str(x) for x in e.args)
                    ))
                print('Sleeping for 5 minutes and trying again.')
                await asyncio.sleep(300)
                continue

            if not league:
                await asyncio.sleep(300)
                continue

            diff = round((datetime.datetime.fromtimestamp(league['end_date'], tz=datetime.timezone.utc)
                          - datetime.datetime.now(tz=datetime.timezone.utc))
                         / datetime.timedelta(seconds=1))

            embed = discord.Embed(title=league['name'], description='League ending soon - any active runs will be cut short.')
            if diff <= 60 * 60 * 24:
                embed.add_field(name='Ending in:', value=dtutil.display_time(diff, 2))
                embed.set_image(url=fetcher.decksite_url('/favicon-152.png'))
                # See #2809.
                # pylint: disable=no-value-for-parameter,unexpected-keyword-arg
                await channel.send(embed=embed)
            if diff <= 5 * 60:
                # Five minutes, final warning.
                timer = 301
            elif diff <= 1 * 60 * 60:
                # 1 hour. Sleep until five minute warning.
                timer = diff - 300
            elif diff <= 24 * 60 * 60:
                # 1 day.  Sleep until one hour warning.
                timer = diff - 1800
            else:
                # Sleep for 1 day, plus enough to leave us with a whole number of days
                timer = 24 * 60 * 60 + diff % (24 * 60 * 60)

            if timer < 300:
                timer = 300
            print('diff={0}, timer={1}'.format(diff, timer))
            await asyncio.sleep(timer)
        print('naturally stopping league reminders')

    @background_task
    async def background_task_rotation_hype(self) -> None:
        rotation_hype_channel_id = configuration.get_int('rotation_hype_channel_id')
        if not rotation_hype_channel_id:
            print('rotation hype channel is not configured')
            return
        channel = self.get_channel(rotation_hype_channel_id)
        while self.is_ready():
            until_rotation = rotation.next_rotation_any_kind() - dtutil.now()
            last_run_time = rotation.last_run_time()
            if until_rotation < datetime.timedelta(7) and last_run_time is not None:
                if dtutil.now() - last_run_time < datetime.timedelta(minutes=5):
                    hype = rotation_hype_message()
                    if hype:
                        await channel.send(hype)
                timer = 5 * 60
            else:
                timer = int((until_rotation - datetime.timedelta(7)).total_seconds())
            await asyncio.sleep(timer)

def init() -> None:
    client = Bot()
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

def rotation_hype_message() -> Optional[str]:
    runs, runs_percent, cs = rotation.read_rotation_files()
    if rotation.next_rotation_is_supplemental():
        cs = [c for c in cs if not c.pd_legal]
    runs_remaining = rotation.TOTAL_RUNS - runs
    newly_legal = [c for c in cs if c.hit_in_last_run and c.hits == rotation.TOTAL_RUNS / 2]
    newly_eliminated = [c for c in cs if not c.hit_in_last_run and c.status == 'Not Legal' and c.hits_needed == runs_remaining + 1]
    newly_hit = [c for c in cs if c.hit_in_last_run and c.hits == 1]
    num_undecided = len([c for c in cs if c.status == 'Undecided'])
    num_legal_cards = len([c for c in cs if c.status == 'Legal'])
    name = 'Supplemental rotation' if rotation.next_rotation_is_supplemental() else 'Rotation'
    s = f'{name} run number {runs} completed. {name} is {runs_percent}% complete. {num_legal_cards} cards confirmed.'
    if newly_hit + newly_legal + newly_eliminated == 0 and runs != 1 and runs % 5 != 0 and runs < rotation.TOTAL_RUNS / 2:
        return None # Sometimes there's nothing to report
    if len(newly_hit) > 0 and runs_remaining > runs:
        newly_hit_s = list_of_most_interesting(newly_hit)
        s += f'\nFirst hit for: {newly_hit_s}.'
    if len(newly_legal) > 0:
        newly_legal_s = list_of_most_interesting(newly_legal)
        s += f'\nConfirmed legal: {newly_legal_s}.'
    if len(newly_eliminated) > 0:
        newly_eliminated_s = list_of_most_interesting(newly_eliminated)
        s += f'\nEliminated: {newly_eliminated_s}.'
    s += f"\nUndecided: {num_undecided}.\n<{fetcher.decksite_url('/rotation/')}>"
    return s

# This does not currently actually find the most interesting just max 10 – only decksite knows about interestingness for now.
def list_of_most_interesting(cs: List[Card]) -> str:
    max_shown = 4
    if len(cs) > max_shown:
        return ', '.join(c.name for c in cs[0:max_shown]) + f' and {len(cs) - max_shown} more'
    return ', '.join(c.name for c in cs)
