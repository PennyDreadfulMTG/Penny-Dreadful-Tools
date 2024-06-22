import asyncio
import logging
import subprocess
from typing import Any

from interactions import Client, listen
from interactions.api.events import MemberAdd, MessageCreate, MessageReactionAdd, PresenceUpdate
from interactions.models import ActivityType, Guild, GuildText, Intents, Member, Role

import discordbot.commands
from discordbot import command
from discordbot.shared import guild_id
from magic import fetcher, multiverse, oracle, whoosh_write
from shared import configuration, perf, repo
from shared import redis_wrapper as redis
from shared.settings import with_config_file


class Bot(Client):
    def __init__(self, **kwargs: Any) -> None:
        self.launch_time = perf.start()
        commit_id = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode()
        redis.store('discordbot:commit_id', commit_id)

        intents = Intents(Intents.DEFAULT | Intents.MESSAGES | Intents.GUILD_PRESENCES | Intents.MESSAGE_CONTENT)

        super().__init__(intents=intents, sync_interactions=True, delete_unused_application_cmds=True, slash_context=command.MtgInteractionContext, **kwargs)
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
