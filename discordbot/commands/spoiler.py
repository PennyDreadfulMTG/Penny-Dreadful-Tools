import asyncio
import logging

from interactions import Client, Extension
from interactions.models import File, slash_command

from discordbot import emoji
from discordbot.command import MtgInteractionContext, slash_card_option
from magic import oracle
from shared import configuration, fetch_tools
from shared.fetch_tools import FetchException


class Spoiler(Extension):
    @slash_command()
    @slash_card_option()
    async def spoiler(self, ctx: MtgInteractionContext, card: str) -> None:
        """Request a card from an upcoming set."""
        if not card:
            await ctx.send(f'{ctx.author.mention}: Please specify a card name.')
            return
        await ctx.defer()
        sfcard = await fetch_tools.fetch_json_async(f'https://api.scryfall.com/cards/named?fuzzy={card}')
        if sfcard['object'] == 'error':
            await ctx.send('{author}: {details}'.format(author=ctx.author.mention, details=sfcard['details']))
            return
        imagename = '{set}_{number}'.format(
            set=sfcard['set'], number=sfcard['collector_number'])
        imagepath = '{image_dir}/{imagename}.jpg'.format(image_dir=configuration.get('image_dir'), imagename=imagename)
        if sfcard.get('card_faces') and sfcard.get('layout', '') != 'split':
            c = sfcard['card_faces'][0]
        else:
            c = sfcard
        image_available = True
        try:
            await asyncio.to_thread(fetch_tools.store_image, c['image_uris']['normal'], imagepath)
        except FetchException as e:
            logging.warning('Could not download image for %s: %s', sfcard['name'], e)
            image_available = False
        text = await emoji.replace_emoji('{name} {mana}'.format(name=sfcard['name'], mana=c['mana_cost']), ctx.bot)
        if image_available:
            await ctx.send(file=File(imagepath), content=text)
        else:
            await ctx.send(content=f'{text}\nImage unavailable.')
        await oracle.scryfall_import_async(sfcard['name'])

def setup(bot: Client) -> None:
    Spoiler(bot)
