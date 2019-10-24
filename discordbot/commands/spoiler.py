from discord import File
from discord.ext import commands

from discordbot import emoji
from discordbot.command import MtgContext
from magic import fetcher, oracle
from shared import configuration


@commands.command(aliases=['sp', 'spoil'])
async def spoiler(ctx: MtgContext, *, args: str) -> None:
    """Request a card from an upcoming set."""
    if len(args) == 0:
        return await ctx.send('{author}: Please specify a card name.'.format(author=ctx.author.mention))
    sfcard = fetcher.internal.fetch_json('https://api.scryfall.com/cards/named?fuzzy={name}'.format(name=args))
    if sfcard['object'] == 'error':
        return await ctx.send('{author}: {details}'.format(author=ctx.author.mention, details=sfcard['details']))
    imagename = '{set}_{number}'.format(
        set=sfcard['set'], number=sfcard['collector_number'])
    imagepath = '{image_dir}/{imagename}.jpg'.format(image_dir=configuration.get('image_dir'), imagename=imagename)
    if sfcard.get('card_faces') and sfcard.get('layout', '') != 'split':
        c = sfcard['card_faces'][0]
    else:
        c = sfcard
    fetcher.internal.store(c['image_uris']['normal'], imagepath)
    text = emoji.replace_emoji('{name} {mana}'.format(name=sfcard['name'], mana=c['mana_cost']), ctx.bot)
    await ctx.send(file=File(imagepath), content=text)
    oracle.scryfall_import(sfcard['name'])
