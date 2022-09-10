import asyncio
import datetime
import logging
import subprocess
from typing import Any, Callable, Dict, List, Optional, cast

from github.GithubException import GithubException
from naff import Client, listen
from naff.api.events import MemberAdd, MessageCreate, MessageReactionAdd, PresenceUpdate
from naff.client.errors import Forbidden
from naff.models import ActivityType, Embed, Guild, GuildText, Intents, Member, Role

import discordbot.commands
from discordbot import command
from discordbot.shared import guild_id
from magic import fetcher, multiverse, oracle, whoosh_write
from shared import configuration, dtutil, fetch_tools, perf
from shared import redis_wrapper as redis
from shared import repo
from shared.settings import with_config_file

TASKS = []

def background_task(func: Callable) -> Callable:
    async def wrapper(self: Client) -> None:
        try:
            await self.wait_until_ready()
            await func(self)
        except Exception as e:
            await self.on_error(func.__name__, e)
    TASKS.append(wrapper)
    return wrapper


class Bot(Client):
    def __init__(self, **kwargs: Any) -> None:
        self.launch_time = perf.start()
        commit_id = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode()
        redis.store('discordbot:commit_id', commit_id)

        intents = Intents(Intents.DEFAULT | Intents.MESSAGES | Intents.GUILD_PRESENCES | Intents.GUILD_MESSAGE_CONTENT)

        super().__init__(intents=intents, sync_interactions=True, delete_unused_application_cmds=True, default_prefix='!',
                         prefixed_context=command.MtgMessageContext, interaction_context=command.MtgInteractionContext,
                         **kwargs)
        self.achievement_cache: Dict[str, Dict[str, str]] = {}
        for task in TASKS:
            asyncio.ensure_future(task(self))
        discordbot.commands.setup(self)
        if configuration.bot_debug.value:
            self.load_extension('naff.ext.debug_extension')
        self.sentry_token = configuration.get_optional_str('sentry_token')
        if self.sentry_token:
            self.load_extension('naff.ext.sentry', token=self.sentry_token)
        self.load_extension('discordbot.background')

    async def stop(self) -> None:
        await super().stop()

    @listen()
    async def on_ready(self) -> None:
        logging.info('Logged in as %s (%d)', self.user, self.user.id)
        names = ', '.join([guild.name or '' for guild in self.guilds])
        logging.info('Connected to %s', names)
        logging.info('--------')

    @listen()
    async def on_startup(self) -> None:
        perf.check(self.launch_time, 'slow_bot_start', '', 'discordbot')

    @listen()
    async def on_message_create(self, event: MessageCreate) -> None:
        if event.message.author.bot:
            return
        if event.message.channel is None:
            logging.warn(f'Got Message with no channel: {event.message}')

        ctx = cast(command.MtgMessageContext, await self.get_context(event.message))  # Casting, because we overrode the base class
        await command.respond_to_card_names(ctx)

    @listen()
    async def on_login(self) -> None:
        token = self.http.token
        if token:
            repo.REDACTED_STRINGS.add(token)

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
            chan = await member.guild.fetch_channel(207281932214599682)  # general (Yes, the guild ID is the same as the ID of it's first channel.  It's not a typo)
            if isinstance(chan, GuildText):
                await chan.send(greeting)
            else:
                logging.warning('could not find greeting channel')

    async def on_presence_update(self, event: PresenceUpdate) -> None:
        user = event.user
        member = await self.fetch_member(user.id, event.guild_id)
        guild = await self.fetch_guild(event.guild_id)
        if member is None:
            return
        if guild is None:
            return
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
                await member.remove_role(streaming_role)
            elif streaming and not streaming_role in member.roles:
                await member.add_role(streaming_role)
        # Achievements
        if event.status in ['online', 'dnd']:
            return await self.sync_achievements(member, guild)

    async def sync_achievements(self, member: Member, guild: Guild) -> None:
        role = await get_role(member.guild, 'Linked Magic Online')
        data = None
        # Linked to PDM
        if role is not None and not role in member.roles:
            if data is None:
                data = await fetcher.person_data_async(member.id)
            if data.get('id', None):
                await member.add_role(role)

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
            await member.remove_roles(remove)
            await member.add_roles(expected)

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
            if c > 0 and reaction.emoji.name == '❎':
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
    async def background_task_league_end(self) -> None:
        tournament_channel_id = configuration.get_int('tournament_reminders_channel_id')
        if not tournament_channel_id:
            logging.warning('tournament channel is not configured')
            return
        try:
            channel = await self.fetch_channel(tournament_channel_id)
        except Forbidden:
            channel = None
            configuration.write('tournament_reminders_channel_id', 0)

        if not isinstance(channel, GuildText):
            logging.warning('tournament channel could not be found')
            return

        while not self.is_closed:
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
            await asyncio.sleep(timer)
        logging.warning('naturally stopping league reminders')

def init() -> None:
    client = Bot()
    logging.info('Connecting to Discord')
    asyncio.run(prepare_database_async())
    client.start(configuration.token.value)

async def prepare_database_async() -> None:
    logging.info('Initializing Cards DB')
    updated = await multiverse.init_async()
    if updated:
        whoosh_write.reindex()
    await multiverse.update_bugged_cards_async()
    oracle.init()


def is_pd_server(guild: Optional[Guild]) -> bool:
    if not guild:
        return False
    return guild.id == configuration.pd_server_id.value

async def get_role(guild: Guild, rolename: str, create: bool = False) -> Optional[Role]:
    for r in guild.roles:
        if r.name == rolename:
            return r
    if create:
        return await guild.create_role(name=rolename)
    return None
