import re

from interactions.client import Client
from interactions.models import Extension, slash_command

from discordbot import command
from discordbot.command import MtgInteractionContext
from magic import image_fetcher
from magic.models import Card


class Art(Extension):
    @slash_command()
    @command.slash_card_option()
    async def art(self, ctx: MtgInteractionContext, card: Card) -> None:
        """Display the artwork of the requested card."""

        if card is not None:
            file_path = re.sub('.jpg$', '.art_crop.jpg', image_fetcher.determine_filepath([card]))
            success = await image_fetcher.download_scryfall_card_image(card, file_path, version='art_crop')
            if success:
                await ctx.send_image_with_retry(file_path)
            else:
                await ctx.send(f'{ctx.author.mention}: Could not get image.')


def setup(bot: Client) -> None:
    Art(bot)
