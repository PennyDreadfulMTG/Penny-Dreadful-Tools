import asyncio
import logging
import sys

from naff import Client, Extension, listen
from naff.models.naff.tasks import IntervalTrigger, Task

from magic import fetcher, image_fetcher
from shared import configuration
from shared import redis_wrapper as redis
from shared import repo


class BackgroundTasks(Extension):
    @listen()
    async def on_startup(self) -> None:
        self.do_banner.start()
        self.do_reboot_key = 'discordbot:do_reboot'
        if redis.get_bool(self.do_reboot_key):
            redis.clear(self.do_reboot_key)
        self.background_task_reboot.start()

    @Task.create(IntervalTrigger(hours=12))
    async def do_banner(self) -> None:
        guild = self.bot.get_guild(configuration.pd_server_id)
        if not guild:
            return

        if not 'BANNER' in guild.features:
            logging.warn('Guild does not have BANNER feature')
            return

        cardnames, background = await fetcher.banner_cards()
        path = await image_fetcher.generate_discord_banner(cardnames, background)

        await guild.edit(banner=path)

    @Task.create(triggers.IntervalTrigger(minutes=1))
    async def background_task_reboot(self) -> None:
        if redis.get_bool(self.do_reboot_key):
            logging.info('Got request to reboot from redis')
            try:
                p = await asyncio.create_subprocess_shell('git pull')
                await p.wait()
                p = await asyncio.create_subprocess_shell(f'{sys.executable} -m pipenv install')
                await p.wait()
            except Exception as c:
                repo.create_issue('Bot error while rebooting', 'discord user', 'discordbot', 'PennyDreadfulMTG/perf-reports', exception=c)
            redis.clear(self.do_reboot_key)
            await self.bot.stop()
            sys.exit(0)

def setup(bot: Client) -> None:
    BackgroundTasks(bot)
