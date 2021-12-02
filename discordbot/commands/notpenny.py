
from discord.ext import commands

from discordbot.command import MtgContext


@commands.command(hidden=True)
@commands.has_permissions(manage_messages=True)
async def notpenny(ctx: MtgContext, args: str) -> None:
    """Don't show PD Legality in this channel"""
    await ctx.send('Command depreciated, use `!configure` instead')
