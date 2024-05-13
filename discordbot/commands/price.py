from interactions import Client
from interactions.models import Extension, slash_command

from discordbot.command import MtgContext, slash_card_option
from magic import card_price
from magic.models import Card


class Price(Extension):
    @slash_command()
    @slash_card_option()
    async def price(self, ctx: MtgContext, card: Card) -> None:
        """Price information for a card."""
        await ctx.single_card_text(card, card_price.card_price_string)


def setup(bot: Client) -> None:
    Price(bot)
