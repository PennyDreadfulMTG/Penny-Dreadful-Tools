import asyncio
import datetime
import logging
import sys

from naff import Client, Extension, listen
from naff.client.errors import Forbidden
from naff.client.utils import timestamp_converter
from naff.models.naff.tasks import IntervalTrigger, Task
from naff.models.discord import GuildText, Embed, ScheduledEventType

from magic import fetcher, image_fetcher, tournaments, multiverse
from shared import configuration, redis_wrapper, dtutil
from shared import repo


class BackgroundTasks(Extension):
    @listen()
    async def on_startup(self) -> None:
        self.do_banner.start()

        self.do_reboot_key = 'discordbot:do_reboot'
        if redis_wrapper.get_bool(self.do_reboot_key):
            redis_wrapper.clear(self.do_reboot_key)
        self.background_task_reboot.start()

        await self.prepare_tournaments()

    @Task.create(IntervalTrigger(hours=12))
    async def do_banner(self) -> None:
        guild = await self.bot.fetch_guild(configuration.pd_server_id)
        if not guild:
            logging.warn('Could not find PD Guild')
            return

        if not 'BANNER' in guild.features:
            logging.warn('Guild does not have BANNER feature')
            return

        cardnames, background = await fetcher.banner_cards()
        path = await image_fetcher.generate_discord_banner(cardnames, background)
        if path == redis_wrapper.get_str('discordbot:bannerpath'):
            logging.info(f'Banner is already {path}')
            return

        logging.info(f'Updating discord banner to {path}')
        await guild.edit(banner=path)

    @Task.create(IntervalTrigger(minutes=1))
    async def background_task_reboot(self) -> None:
        if redis_wrapper.get_bool(self.do_reboot_key):
            logging.info('Got request to reboot from redis')
            try:
                p = await asyncio.create_subprocess_shell('git pull')
                await p.wait()
                p = await asyncio.create_subprocess_shell(f'{sys.executable} -m pipenv install')
                await p.wait()
            except Exception as c:
                repo.create_issue('Bot error while rebooting', 'discord user', 'discordbot', 'PennyDreadfulMTG/perf-reports', exception=c)
            redis_wrapper.clear(self.do_reboot_key)
            await self.bot.stop()
            sys.exit(0)

    async def prepare_tournaments(self) -> None:
        tournament_channel_id = configuration.get_int('tournament_reminders_channel_id')
        if not tournament_channel_id:
            logging.warning('tournament channel is not configured')
            return
        try:
            channel = await self.bot.fetch_channel(tournament_channel_id)
        except Forbidden:
            channel = None
            configuration.write('tournament_reminders_channel_id', 0)

        if not isinstance(channel, GuildText):
            logging.warning('ERROR: could not find tournament_channel_id %d', tournament_channel_id)
            return
        self.tournament_reminders_channel = channel
        self.background_task_tournaments.start()

    @Task.create(IntervalTrigger(minutes=1))
    async def background_task_tournaments(self) -> IntervalTrigger:
        guild = self.tournament_reminders_channel.guild
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
            await self.tournament_reminders_channel.send(embed=embed)

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
        events = await guild.list_scheduled_events()
        created = any(e.name == info['next_tournament_name'] for e in events)
        if not created:
            try:
                expected_duration = datetime.timedelta(hours=3)  # Maybe vary this based on event name?
                await guild.create_scheduled_event(
                    name=info['next_tournament_name'],
                    description=message,
                    start_time=timestamp_converter(info['time']),
                    end_time=timestamp_converter(info['time'] + expected_duration),
                    event_type=ScheduledEventType.EXTERNAL,
                    external_location='https://gatherling.com',
                )
            except Forbidden:
                logging.warning('Can\t create scheduled events')
        return IntervalTrigger(timer)

def setup(bot: Client) -> None:
    BackgroundTasks(bot)
