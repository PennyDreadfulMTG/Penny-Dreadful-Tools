from discord import File
from discord.ext import commands

from discordbot import emoji
from discordbot.command import MtgContext
from magic import oracle
from shared import configuration, fetch_tools


@commands.command(aliases=['sp', 'spoil'])
async def spoiler(ctx: MtgContext, *, args: str) -> None:
    """Request a card from an upcoming set."""
    if len(args) == 0:
        await ctx.send('{author}: Please specify a card name.'.format(author=ctx.author.mention))
        return
    sfcard = fetch_tools.fetch_json('https://api.scryfall.com/cards/named?fuzzy={name}'.format(name=args))
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
    fetch_tools.store(c['image_uris']['normal'], imagepath)
    text = emoji.replace_emoji('{name} {mana}'.format(name=sfcard['name'], mana=c['mana_cost']), ctx.bot)
    await ctx.send(file=File(imagepath), content=text)
    await oracle.scryfall_import_async(sfcard['name'])
