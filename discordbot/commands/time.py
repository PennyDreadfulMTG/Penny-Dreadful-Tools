import logging
import re

from interactions import Client, Extension
from interactions.models import OptionType, slash_command, slash_option

from discordbot.command import MtgContext
from discordbot.shared import guild_id
from magic import fetcher
from shared import configuration
from shared.pd_exception import NotConfiguredException, TooFewItemsException
from shared.settings import with_config_file


class Time(Extension):
    @slash_command('time')
    @slash_option('place', 'Where are you checking the time?', OptionType.STRING, required=True)
    async def time(self, ctx: MtgContext, place: str) -> None:
        """Current time in location."""
        if not place:
            await ctx.send(f'{ctx.author.mention}: No location provided. Please type !time followed by the location you want the time for.')
            return
        try:
            with with_config_file(guild_id(ctx.channel)), with_config_file(ctx.channel.id):
                twentyfour = configuration.use_24h.value
            ts = fetcher.time(place, twentyfour)
            times_s = ''
            for t, zones in ts.items():
                cities = sorted({re.sub('.*/(.*)', '\\1', zone).replace('_', ' ') for zone in zones})
                times_s += '{cities}: {t}\n'.format(cities=', '.join(cities), t=t)
            await ctx.send(times_s)
        except NotConfiguredException:
            await ctx.send('The time command has not been configured.')
        except TooFewItemsException:
            logging.exception('Exception trying to get the time for %s.', place)
            await ctx.send(f'{ctx.author.mention}: Location not found.')

def setup(bot: Client) -> None:
    Time(bot)
