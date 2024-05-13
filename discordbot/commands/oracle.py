from interactions import Client
from interactions.models import Extension, slash_command

from discordbot.command import MtgContext, slash_card_option
from magic.models import Card


class Oracle(Extension):
    @slash_command()
    @slash_card_option()
    async def oracle(self, ctx: MtgContext, card: Card) -> None:
        """Oracle text of a card."""
        await ctx.single_card_text(card, oracle_text)

def oracle_text(c: Card) -> str:
    return c.oracle_text

def setup(bot: Client) -> None:
    Oracle(bot)
