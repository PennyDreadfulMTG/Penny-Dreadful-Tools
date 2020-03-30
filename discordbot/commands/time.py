import logging
import re

from discord.ext import commands

from discordbot.command import MtgContext, guild_or_channel_id
from magic import fetcher
from shared import configuration
from shared.pd_exception import NotConfiguredException, TooFewItemsException


@commands.command(aliases=['t'])
async def time(ctx: MtgContext, *, args: str) -> None:
    """Current time in location."""
    if len(args) == 0:
        await ctx.send('{author}: No location provided. Please type !time followed by the location you want the time for.'.format(author=ctx.author.mention))
        return
    try:
        twentyfour = configuration.get_bool(f'{guild_or_channel_id(ctx.channel)}.use_24h') or configuration.get_bool(f'{ctx.channel.id}.use_24h')
        ts = fetcher.time(args, twentyfour)
        times_s = ''
        for t, zones in ts.items():
            cities = sorted(set(re.sub('.*/(.*)', '\\1', zone).replace('_', ' ') for zone in zones))
            times_s += '{cities}: {t}\n'.format(cities=', '.join(cities), t=t)
        await ctx.send(times_s)
    except NotConfiguredException:
        await ctx.send('The time command has not been configured.')
    except TooFewItemsException:
        logging.exception('Exception trying to get the time for %s.', args)
        await ctx.send('{author}: Location not found.'.format(author=ctx.author.mention))
