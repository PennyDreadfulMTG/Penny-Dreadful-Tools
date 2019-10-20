import subprocess
from discord.ext import commands

from discordbot.command import MtgContext
from magic import database

@commands.command(hidden=True)
async def version(ctx: MtgContext) -> None:
    """Display the current version numbers"""
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], universal_newlines=True).strip('\n').strip('"')
    scryfall = database.last_updated()
    return await ctx.send(f'I am currently running mtgbot version `{commit}`, and scryfall last updated `{scryfall}`')
