import re

from discord.ext import commands

from discordbot.command import MtgContext
from magic import image_fetcher
from magic.models import Card


@commands.command(aliases=['a'])
async def art(ctx: MtgContext, *, c: Card) -> None:
    """`!art {name}` Art (only) of the most recent printing of a card."""
    if c is not None:
        file_path = re.sub('.jpg$', '.art_crop.jpg', image_fetcher.determine_filepath([c]))
        if image_fetcher.download_scryfall_card_image(c, file_path, version='art_crop'):
            await ctx.send_image_with_retry(file_path)
        else:
            await ctx.send('{author}: Could not get image.'.format(author=ctx.author.mention))
