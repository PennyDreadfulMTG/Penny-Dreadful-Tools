from dis_snek import Snake
from dis_snek.models.application_commands import slash_command
from dis_snek.models.scale import Scale

from discordbot.command import MtgContext, autocomplete_card, slash_card_option
from magic.models import Card


class Oracle(Scale):
    @slash_command('oracle')
    @slash_card_option()
    async def oracle(ctx: MtgContext, card: Card) -> None:
        """Oracle text of a card."""
        await ctx.single_card_text(card, oracle_text)

    oracle.autocomplete('card')(autocomplete_card)

def oracle_text(c: Card) -> str:
    return c.oracle_text

def setup(bot: Snake) -> None:
    Oracle(bot)
