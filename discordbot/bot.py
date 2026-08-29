import asyncio
import datetime
import logging
import os
import subprocess
from typing import Any, cast

from interactions import Client, listen
from interactions.api.events import CommandError, MemberAdd, MessageCreate, MessageReactionAdd, PresenceUpdate
from interactions.client.errors import CommandCheckFailure, CommandOnCooldown, MaxConcurrencyReached
from interactions.models import ActivityType, Guild, GuildText, Intents, Member, Role

import discordbot.commands
from discordbot import command, error_handling
from discordbot.shared import guild_id
from magic import fetcher, multiverse, oracle, whoosh_write
from shared import configuration, perf, repo
from shared import redis_wrapper as redis
from shared.settings import with_config_file

COMMAND_SYNC_ATTEMPTS = 3
COMMAND_SYNC_RETRY_SECONDS = 5


class Bot(Client):
    def __init__(self, **kwargs: Any) -> None:
        error_handling.configure_logging()
        self.launch_time = perf.start()
        self.started_at = datetime.datetime.now(datetime.UTC)
        self.commit_id = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
        self._shutdown_lock = asyncio.Lock()
        self._shutdown_complete = False
        redis.store('discordbot:commit_id', self.commit_id)

        intents = Intents(Intents.DEFAULT | Intents.MESSAGES | Intents.GUILD_PRESENCES | Intents.MESSAGE_CONTENT)

        super().__init__(intents=intents, sync_interactions=True, delete_unused_application_cmds=True, send_command_tracebacks=False, slash_context=command.MtgInteractionContext, **kwargs)
        self.achievement_cache: dict[str, dict[str, str]] = {}
        discordbot.commands.setup(self)
        if configuration.bot_debug.value:
            self.load_extension('interactions.ext.debug_extension')
            self.load_extension('interactions.ext.jurigged')
        self.sentry_token = configuration.get_optional_str('sentry_token')
        if self.sentry_token:
            self.load_extension('interactions.ext.sentry', token=self.sentry_token)
        self.load_extension('discordbot.background')

        self.add_global_autocomplete(command.autocomplete_card)

    async def _init_interactions(self) -> None:
        for attempt in range(1, COMMAND_SYNC_ATTEMPTS + 1):
            try:
                if self.sync_interactions:
                    await self.synchronise_interactions()
                else:
                    await self._cache_interactions(warn_missing=False)

                missing_commands = {cmd.resolved_name for cmd in self.application_commands} - self._interaction_lookup.keys()
                if missing_commands:
                    raise RuntimeError(f'Discord command cache is missing {len(missing_commands)} application commands')
                if attempt > 1:
                    logging.info('Discord command sync succeeded on attempt %d', attempt)
                return
            except Exception:
                if attempt == COMMAND_SYNC_ATTEMPTS:
                    logging.critical('Discord command sync failed after %d attempts; exiting for restart', attempt, exc_info=True)
                    os._exit(1)
                    return
                delay = COMMAND_SYNC_RETRY_SECONDS * 2 ** (attempt - 1)
                logging.warning('Discord command sync failed on attempt %d/%d; retrying in %d seconds', attempt, COMMAND_SYNC_ATTEMPTS, delay, exc_info=True)
                await asyncio.sleep(delay)

    async def stop(self) -> None:
        async with self._shutdown_lock:
            if self._shutdown_complete:
                return
            self._ready.clear()
            # interactions.py closes HTTP before the gateway, allowing the
            # heartbeat task to write to an already-closing WebSocket.
            await self._connection_state.stop()
            await self.http.close()
            self._shutdown_complete = True

    @listen()
    async def on_ready(self) -> None:
        logging.info('Logged in as %s (%d)', self.user, self.user.id)
        names = ', '.join([guild.name or '' for guild in self.guilds])
        logging.info('Connected to %s', names)
        logging.info('--------')

    @listen()
    async def on_startup(self) -> None:
        perf.check(self.launch_time, 'slow_bot_start', '', 'discordbot')

    @listen(disable_default_listeners=True)
    async def on_command_error(self, event: CommandError) -> None:
        ctx = cast(command.MtgInteractionContext, event.ctx)
        if isinstance(event.error, CommandOnCooldown):
            await ctx.send(f'This command is on cooldown. Try again in {int(event.error.cooldown.get_cooldown_time())} seconds.')
            return
        if isinstance(event.error, MaxConcurrencyReached):
            await ctx.send('This command is already busy. Please try again shortly.')
            return
        if isinstance(event.error, CommandCheckFailure):
            await ctx.send('You do not have permission to run this command.')
            return
        error_handling.log_exception(event.error, f'Unhandled error in /{ctx.invoke_target}')
        await ctx.send(error_handling.public_message(event.error))

    @listen()
    async def on_message_create(self, event: MessageCreate) -> None:
        if event.message.author.bot:
            return
        if event.message.channel is None:
            logging.warning(f'Got Message with no channel: {event.message}')
        if event.message.channel.id == configuration.honeypot_channel_id.value:
            author = event.message.author
            if isinstance(author, Member):
                await author.ban(delete_message_days=1, reason='Spambot detected by posting in honeypot channel')
            return

        ctx = command.MtgMessageContext.from_message(self, event.message)
        await command.respond_to_card_names(ctx)

    @listen()
    async def on_login(self) -> None:
        token = self.http.token
        if token:
            repo.REDACTED_STRINGS.add(token)

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
            elif streaming and streaming_role not in member.roles:
                await member.add_role(streaming_role)
        # Achievements
        if event.status in ['online', 'dnd']:
            return await self.sync_achievements(member, guild)

    async def sync_achievements(self, member: Member, guild: Guild) -> None:
        role = await get_role(member.guild, 'Linked Magic Online')
        data = None
        # Linked to PDM
        if role is not None and role not in member.roles:
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
            expected: list[Role] = []
            remove: list[Role] = []

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


def is_pd_server(guild: Guild | None) -> bool:
    if not guild:
        return False
    return guild.id == configuration.pd_server_id.value

async def get_role(guild: Guild, rolename: str, create: bool = False) -> Role | None:
    for r in guild.roles:
        if r.name == rolename:
            return r
    if create:
        return await guild.create_role(name=rolename)
    return None
