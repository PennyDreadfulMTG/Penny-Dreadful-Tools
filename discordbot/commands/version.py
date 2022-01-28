import subprocess

from importlib.metadata import version as _v
from dis_snek.models import slash_command, Embed

from discordbot.command import MtgContext
from magic import database


@slash_command('version')
async def version(ctx: MtgContext) -> None:
    """Display the current version numbers"""
    embed = Embed('Version')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], universal_newlines=True).strip('\n').strip('"')
    embed.add_field('Commit hash', commit)
    age = subprocess.check_output(['git', 'show', '-s', '--format=%ci ', 'HEAD'], universal_newlines=True).strip('\n').strip('"')
    embed.add_field('Commit age', age)
    scryfall = database.last_updated()
    embed.add_field('Scryfall last updated', scryfall)
    snekver = _v('dis-snek')
    embed.add_field('dis-snek version', snekver)
    await ctx.send(embed=embed)
