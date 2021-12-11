import asyncio
import datetime
import logging
import os
import subprocess
import sys
from typing import Any, Callable, Dict, List, Optional

import sentry_sdk
from dis_snek import Snake
from dis_snek.errors import Forbidden
from dis_snek.models.discord_objects.activity import ActivityType
from dis_snek.models.discord_objects.channel import GuildText
from dis_snek.models.discord_objects.embed import Embed
from dis_snek.models.discord_objects.guild import Guild
from dis_snek.models.discord_objects.role import Role
from dis_snek.models.discord_objects.user import Member, User
from dis_snek.models.enums import Intents
from dis_snek.models.events.discord import (MemberAdd, MessageCreate, MessageReactionAdd,
                                            PresenceUpdate)
from dis_snek.models.listener import listen
from github.GithubException import GithubException

import discordbot.commands
from discordbot import command
from discordbot.shared import guild_id
from magic import fetcher, multiverse, oracle, rotation, seasons, tournaments, whoosh_write
from magic.models import Card
from shared import configuration, dtutil, fetch_tools, perf
from shared import redis_wrapper as redis
from shared import repo
from shared.settings import with_config_file


def sentry_filter(event, hint):  # type: ignore
    if 'log_record' in hint:
        record: logging.LogRecord = hint['log_record']
        if 'dis.snek' in record.name and '/commands/permissions: 403' in record.message:
            return None

    if 'exc_info' in hint:
        exc_type, exc_value, tb = hint['exc_info']
        if isinstance(exc_value, OSError):
            return None
    return event


sentry_token = configuration.get_optional_str('sentry_token')
if sentry_token:
    try:
        sentry_sdk.init(
            dsn=sentry_token,
            integrations=[],
            before_send=sentry_filter,
        )
    except Exception as c:  # pylint: disable=broad-except
        logging.error(c)

TASKS = []

def background_task(func: Callable) -> Callable:
    async def wrapper(self: Snake) -> None:
        try:
            await self.wait_until_ready()
            await func(self)
        except Exception as e:
            await self.on_error(func.__name__, e)
    TASKS.append(wrapper)
    return wrapper


class Bot(Snake):
    def __init__(self, **kwargs: Any) -> None:
        self.launch_time = perf.start()
        self.launched = False
        commit_id = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode()
        redis.store('discordbot:commit_id', commit_id)

        intents = Intents(Intents.DEFAULT | Intents.MESSAGES | Intents.GUILD_PRESENCES)

        super().__init__(intents, sync_interactions=True, delete_unused_application_cmds=False, default_prefix='!', **kwargs)
        self.achievement_cache: Dict[str, Dict[str, str]] = {}
        for task in TASKS:
            asyncio.ensure_future(task(self), loop=self.loop)
        discordbot.commands.setup(self)
        if configuration.bot_debug.value:
            self.grow_scale('dis_snek.debug_scale')

    async def stop(self) -> None:
        await super().stop()

    @listen()
    async def on_ready(self) -> None:
        logging.info('Logged in as %s (%d)', self.user, self.user.id)
        names = ', '.join([guild.name or '' for guild in self.guilds])
        logging.info('Connected to %s', names)
        logging.info('--------')
        if not self.launched:
            perf.check(self.launch_time, 'slow_bot_start', '', 'discordbot')
            self.launched = True

    @listen()
    async def on_message_create(self, event: MessageCreate) -> None:
        if event.message.author.bot:
            return
        if event.message.channel is None:
            logging.warn(f'Got Message with no channel: {event.message}')

        await command.respond_to_card_names(event.message, self)

    # async def on_voice_state_update(self, member: Member, before: VoiceState, after: VoiceState) -> None:
    #     # pylint: disable=unused-argument
    #     # If we're the only one left in a voice chat, leave the channel
    #     guild = getattr(after.channel, 'guild', None)
    #     if guild is None:
    #         return
    #     voice = guild.voice_client
    #     if voice is None or not voice.is_connected():
    #         return
    #     if len(voice.channel.voice_members) == 1:
    #         await voice.disconnect()

    async def on_member_add(self, event: MemberAdd) -> None:
        member: Member = event.member
        if member.bot:
            return
        if is_pd_server(member.guild):
            greeting = "Hey there {mention}, welcome to the Penny Dreadful community!  Be sure to set your nickname to your MTGO username, and check out <{url}> if you haven't already.".format(mention=member.mention, url=fetcher.decksite_url('/'))
            chan = await member.guild.get_channel(207281932214599682)  # general (Yes, the guild ID is the same as the ID of it's first channel.  It's not a typo)
            await chan.send(greeting)

    async def on_presence_update(self, event: PresenceUpdate) -> None:
        user: User = event.user
        member: Member = await self.get_member(user.id, event.guild_id)
        guild: Guild = await self.get_guild(event.guild_id)
        if user.bot:
            return
        # streamers
        streaming_role = await get_role(guild, 'Currently Streaming')
        if streaming_role:
            streaming = False
            for activity in event.activities:
                if activity.type == ActivityType.STREAMING:
                    streaming = True
            if not streaming and streaming_role in member.roles:
                await member.remove_roles(streaming_role)
            elif streaming and not streaming_role in member.roles:
                await member.add_roles(streaming_role)
        # Achievements
        role = await get_role(member.guild, 'Linked Magic Online')
        if role and event.status in ['online', 'dnd']:
            data = None
            # Linked to PDM
            if role is not None and not role in member.roles:
                if data is None:
                    data = await fetcher.person_data_async(member.id)
                if data.get('id', None):
                    await member.add_roles(role)

            key = f'discordbot:achievements:players:{member.id}'
            if is_pd_server(guild) and not redis.get_bool(key) and not data:
                data = await fetcher.person_data_async(member.id)
                redis.store(key, True, ex=14400)

            # Trophies
            if is_pd_server(guild) and data is not None and data.get('achievements', None) is not None:
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
                        role = await get_role(guild, trophy, create=True)
                        if role is not None:
                            expected.append(role)
                for role in member.roles:
                    if role in expected:
                        expected.remove(role)
                    elif '🏆' in role.name:
                        remove.append(role)
                await member.remove_roles(*remove)
                await member.add_roles(*expected)

    # async def on_guild_join(self, server: Guild) -> None:
    #     for channel in server.channels:
    #         if isinstance(channel, GuildText):
    #             try:
    #                 await channel.send("Hi, I'm mtgbot.  To look up cards, just mention them in square brackets. (eg `[Llanowar Elves] is better than [Elvish Mystic]`).")
    #                 await channel.send("By default, I display Penny Dreadful legality. If you don't want or need that, just type `!notpenny`.")
    #                 return
    #             except Exception:  # noqa
    #                 pass

    @listen()
    async def on_message_reaction_add(self, event: MessageReactionAdd) -> None:
        for i in range(len(event.message.reactions)):
            r = event.message.reactions[i]
            if r.emoji == event.emoji:
                reaction = r
                break
        else:
            return

        if reaction.message.author == self.user:
            c = reaction.count
            with with_config_file(guild_id(reaction.message.channel)), with_config_file(reaction.message.channel.id):
                dismissable = configuration.dismiss_any
            if reaction.me:
                c = c - 1
            elif not dismissable:
                return
            if c > 0 and not reaction.custom_emoji and reaction.emoji == '❎':
                await reaction.message.delete()
            # elif c > 0 and 'Ambiguous name for ' in reaction.message.content and reaction.emoji in command.DISAMBIGUATION_EMOJIS_BY_NUMBER.values():
            #     async with reaction.message.channel.typing():
            #         search = re.search(r'Ambiguous name for ([^\.]*)\. Suggestions: (.*)', reaction.message.content)
            #         if search:
            #             previous_command, suggestions = search.group(1, 2)
            #             card = re.findall(r':[^:]*?: ([^:]*) ', suggestions + ' ')[command.DISAMBIGUATION_NUMBERS_BY_EMOJI[reaction.emoji] - 1]
            #             # pylint: disable=protected-access
            #             message = Container(content='!{c} {a}'.format(c=previous_command, a=card), channel=reaction.message.channel, author=author, reactions=[], _state=reaction.message._state)
            #             await self.on_message(message)
            #             await reaction.message.delete()

    async def on_error(self, source: str, error: Exception, *args: Any, **kwargs: Any) -> None:
        await super().on_error(source, error, *args, **kwargs)
        try:
            content = [arg.content for arg in args if hasattr(arg, 'content')]  # The default string representation of a Message does not include the message content.
            repo.create_issue(f'Bot error {source}\n{args}\n{kwargs}\n{content}', 'discord user', 'discordbot', 'PennyDreadfulMTG/perf-reports', exception=error)
        except GithubException as e:
            logging.error('Github error\n%s', e)

    @background_task
    async def background_task_tournaments(self) -> None:
        tournament_channel_id = configuration.get_int('tournament_reminders_channel_id')
        if not tournament_channel_id:
            logging.warning('tournament channel is not configured')
            return
        try:
            channel = await self.get_channel(tournament_channel_id)
        except Forbidden:
            channel = None
            configuration.write('tournament_reminders_channel_id', 0)

        if not isinstance(channel, GuildText):
            logging.warning('ERROR: could not find tournament_channel_id %d', tournament_channel_id)
            return
        while self.is_ready:
            info = tournaments.next_tournament_info()
            diff = info['next_tournament_time_precise']
            if info['sponsor_name']:
                message = 'A {sponsor} sponsored tournament'.format(sponsor=info['sponsor_name'])
            else:
                message = 'A free tournament'
            embed = Embed(title=info['next_tournament_name'], description=message)
            if diff <= 1:
                embed.add_field(name='Starting now', value='Check <#334220558159970304> for further annoucements')
            elif diff <= 14400:
                embed.add_field(name='Starting in:', value=dtutil.display_time(diff, 2))
                embed.add_field(name='Pre-register now:', value='https://gatherling.com')

            if diff <= 14400:
                embed.set_image(url=fetcher.decksite_url('/favicon-152.png'))
                # See #2809.
                # pylint: disable=no-value-for-parameter,unexpected-keyword-arg
                await channel.send(embed)

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
                    await multiverse.update_bugged_cards_async()

            if timer < 300:
                timer = 300
            await asyncio.sleep(timer)
        logging.warning('naturally stopping tournament reminders')

    @background_task
    async def background_task_league_end(self) -> None:
        tournament_channel_id = configuration.get_int('tournament_reminders_channel_id')
        if not tournament_channel_id:
            logging.warning('tournament channel is not configured')
            return
        try:
            channel = await self.get_channel(tournament_channel_id)
        except Forbidden:
            channel = None
            configuration.write('tournament_reminders_channel_id', 0)

        if not isinstance(channel, GuildText):
            logging.warning('tournament channel could not be found')
            return

        while self.is_ready:
            try:
                league = await fetch_tools.fetch_json_async(fetcher.decksite_url('/api/league'))
            except fetch_tools.FetchException as e:
                err = '; '.join(str(x) for x in e.args)
                logging.error("Couldn't reach decksite or decode league json with error message(s) %s", err)
                logging.info('Sleeping for 5 minutes and trying again.')
                await asyncio.sleep(300)
                continue

            if not league:
                await asyncio.sleep(300)
                continue

            diff = round((dtutil.parse_rfc3339(league['end_date'])
                          - datetime.datetime.now(tz=datetime.timezone.utc))
                         / datetime.timedelta(seconds=1))

            embed = Embed(title=league['name'], description='League ending soon - any active runs will be cut short.')
            if diff <= 60 * 60 * 24:
                embed.add_field(name='Ending in:', value=dtutil.display_time(diff, 2))
                embed.set_image(url=fetcher.decksite_url('/favicon-152.png'))
                # See #2809.
                # pylint: disable=no-value-for-parameter,unexpected-keyword-arg
                await channel.send(embed)
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
            await asyncio.sleep(timer)
        logging.warning('naturally stopping league reminders')

    @background_task
    async def background_task_rotation_hype(self) -> None:
        rotation_hype_channel_id = configuration.get_int('rotation_hype_channel_id')
        if not rotation_hype_channel_id:
            logging.warning('rotation hype channel is not configured')
            return
        try:
            channel = await self.get_channel(rotation_hype_channel_id)
        except Forbidden:
            channel = None
            configuration.write('rotation_hype_channel_id', 0)

        if not isinstance(channel, GuildText):
            logging.warning('rotation hype channel is not a text channel')
            return
        while True:
            until_rotation = seasons.next_rotation() - dtutil.now()
            last_run_time = rotation.last_run_time()
            if os.path.exists('.rotation.lock'):
                timer = 10
            elif until_rotation < datetime.timedelta(7) and last_run_time is not None:
                if dtutil.now() - last_run_time < datetime.timedelta(minutes=5):
                    hype = await rotation_hype_message(False)
                    if hype:
                        await channel.send(hype)
                timer = 5 * 60
            else:
                timer = int((until_rotation - datetime.timedelta(7)).total_seconds())
            await asyncio.sleep(timer)

    @background_task
    async def background_task_reboot(self) -> None:
        do_reboot_key = 'discordbot:do_reboot'
        if redis.get_bool(do_reboot_key):
            redis.clear(do_reboot_key)
        while True:
            if redis.get_bool(do_reboot_key):
                logging.info('Got request to reboot from redis')
                try:
                    p = await asyncio.create_subprocess_shell('git pull')
                    await p.wait()
                    p = await asyncio.create_subprocess_shell(f'{sys.executable} -m pipenv install')
                    await p.wait()
                except Exception as c:
                    repo.create_issue('Bot error while rebooting', 'discord user', 'discordbot', 'PennyDreadfulMTG/perf-reports', exception=c)
                await self.stop()
                sys.exit(0)
            await asyncio.sleep(60)

def init() -> None:
    client = Bot()
    logging.info('Initializing Cards DB')
    updated = multiverse.init()
    if updated:
        whoosh_write.reindex()
    asyncio.ensure_future(multiverse.update_bugged_cards_async())
    oracle.init()
    logging.info('Connecting to Discord')
    client.start(configuration.get_str('token'))

def is_pd_server(guild: Guild) -> bool:
    return guild.id == 207281932214599682  # or guild.id == 226920619302715392

async def get_role(guild: Guild, rolename: str, create: bool = False) -> Optional[Role]:
    for r in guild.roles:
        if r.name == rolename:
            return r
    if create:
        return await guild.create_role(name=rolename)
    return None

async def rotation_hype_message(hype_command: bool) -> Optional[str]:
    if not hype_command:
        rotation.clear_redis()
    runs, runs_percent, cs = rotation.read_rotation_files()
    runs_remaining = rotation.TOTAL_RUNS - runs
    newly_legal = [c for c in cs if c.hit_in_last_run and c.hits == rotation.TOTAL_RUNS / 2]
    newly_eliminated = [c for c in cs if not c.hit_in_last_run and c.status == 'Not Legal' and c.hits_needed == runs_remaining + 1]
    newly_hit = [c for c in cs if c.hit_in_last_run and c.hits == 1]
    num_undecided = len([c for c in cs if c.status == 'Undecided'])
    num_legal_cards = len([c for c in cs if c.status == 'Legal'])
    if not newly_hit + newly_legal + newly_eliminated and runs != 1 and runs % 5 != 0 and runs < rotation.TOTAL_RUNS / 2 and not hype_command:
        return None  # Sometimes there's nothing to report
    s = f'Rotation run number {runs} completed.'
    if hype_command:
        s = f'{runs} rotation checks have completed.'
    s += f' Rotation is {runs_percent}% complete. {num_legal_cards} cards confirmed.'
    if len(newly_hit) > 0 and runs_remaining > runs:
        newly_hit_s = list_of_most_interesting(newly_hit)
        s += f'\nFirst hit for: {newly_hit_s}.'
    if len(newly_legal) > 0:
        newly_legal_s = list_of_most_interesting(newly_legal)
        s += f'\nConfirmed legal: {newly_legal_s}.'
    if len(newly_eliminated) > 0:
        newly_eliminated_s = list_of_most_interesting(newly_eliminated)
        s += f'\nEliminated: {newly_eliminated_s}.'
    s += f'\nUndecided: {num_undecided}.\n'
    if runs_percent >= 50:
        s += f"<{fetcher.decksite_url('/rotation/')}>"
    return s

# This does not currently actually find the most interesting just max 10 – only decksite knows about interestingness for now.
def list_of_most_interesting(cs: List[Card]) -> str:
    max_shown = 4
    if len(cs) > max_shown:
        return ', '.join(c.name for c in cs[0:max_shown]) + f' and {len(cs) - max_shown} more'
    return ', '.join(c.name for c in cs)
