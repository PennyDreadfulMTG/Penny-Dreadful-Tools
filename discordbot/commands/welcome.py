from interactions import Client, Extension
from interactions.models import slash_command

from discordbot.command import MtgContext, MtgInteractionContext
from magic import image_fetcher, oracle
from magic.models import Card


class Welcome(Extension):
    @slash_command(description='Welcome a newcomer to PD.')
    async def welcome(self, ctx: MtgInteractionContext) -> None:
        """Welcome a newcomer to PD."""
        await ctx.defer()
        text = 'Welcome! Let us know if you have any questions.'
        card = oracle.cards_by_name()['Welcome to the Fold']
        await greeting(ctx, card, text)

    @slash_command('back-for-more', description='Greet someone returning to PD.')
    async def back_for_more(self, ctx: MtgInteractionContext) -> None:
        """Greet someone returning to PD."""
        await ctx.defer()
        card = oracle.cards_by_name()['Back for More']
        await greeting(ctx, card)

async def greeting(ctx: MtgContext, card: Card, text: str = '') -> None:
    file_path = image_fetcher.determine_filepath([card])
    success = await image_fetcher.download_scryfall_card_image(card, file_path, version='png')
    if success:
        await ctx.send_image_with_retry(file_path, text)
    else:
        await ctx.send(text)

def setup(bot: Client) -> None:
    Welcome(bot)
