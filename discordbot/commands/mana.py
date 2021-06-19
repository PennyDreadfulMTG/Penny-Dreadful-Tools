import os
import pathlib

import discord
from discord.ext import commands

from discordbot.command import MtgContext


@commands.command(aliases=['frank'])
async def mana(ctx: MtgContext) -> None:
    """Get Dr. Karsten's advice on number of colored sources of mana required."""
    with open(os.path.join(pathlib.Path(__file__).parent.absolute(), 'img/mana-frank.png'), 'rb') as f:
        img = discord.File(f)
        await ctx.channel.send(file=img)
