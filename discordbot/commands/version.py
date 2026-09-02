import datetime
import logging
import os
import subprocess
from importlib.metadata import version as _v

from interactions import Client, Extension, Timestamp
from interactions.models import Embed, slash_command

from discordbot.command import MtgContext
from magic import database
from shared.pd_exception import DatabaseException


class Version(Extension):
    @slash_command('version', description='Display the current version numbers.')
    async def version(self, ctx: MtgContext) -> None:
        """Display the current version numbers"""
        embed = Embed(title='Version')
        checkout_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
        loaded_commit = getattr(ctx.bot, 'commit_id', checkout_commit)
        embed.add_field('Loaded commit', loaded_commit)
        if checkout_commit != loaded_commit:
            embed.add_field('Checkout commit', checkout_commit)
        age = subprocess.check_output(['git', 'show', '-s', '--format=%ct', loaded_commit], text=True).strip()
        embed.add_field('Loaded commit age', Timestamp.fromtimestamp(int(age)))
        started_at = getattr(ctx.bot, 'started_at', None)
        if isinstance(started_at, datetime.datetime):
            embed.add_field('Process started', Timestamp.fromdatetime(started_at))
        embed.add_field('Process ID', str(os.getpid()))
        try:
            scryfall = Timestamp.fromdatetime(database.last_updated())
            embed.add_field('Scryfall last updated', scryfall)
        except DatabaseException as e:
            logging.warning('Could not get the Scryfall update time for /version: %s', e)
            embed.add_field('Scryfall last updated', 'Unavailable (database error)')
        snekver = _v('interactions.py')
        embed.add_field('interactions version', snekver)
        await ctx.send(embed=embed)

def setup(bot: Client) -> None:
    Version(bot)
