from interactions import Client
from interactions.models import Extension, slash_command

from discordbot import command
from discordbot.command import MtgContext
from magic.models import Card


class Legal(Extension):
    @slash_command('legal')
    @command.slash_card_option()
    async def legal(self, ctx: MtgContext, card: Card) -> None:
        """Announce whether the specified card is legal or not."""
        await ctx.single_card_text(card, lambda c: '')

def setup(bot: Client) -> None:
    Legal(bot)
