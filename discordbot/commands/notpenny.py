
from discord.ext import commands

from discordbot.command import MtgContext
from shared import configuration

@commands.command
async def notpenny(ctx: MtgContext, args: str) -> None:
    """Don't show PD Legality in this channel"""
    existing = configuration.get_list('not_pd')
    if args == 'server' and getattr(ctx.channel, 'guild', None) is not None:
        cid = ctx.channel.guild.id
    else:
        cid = ctx.channel.id
    if str(cid) not in existing:
        existing.append(str(cid))
        configuration.write('not_pd', set(existing))
    if args == 'server':
        await ctx.send('Disable PD legality marks for the entire server')
    else:
        await ctx.send('Disable PD legality marks for this channel. If you wanted to disable for the entire server, use `!notpenny server` instead.')
