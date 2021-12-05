from dis_snek import Snake
from dis_snek.models.application_commands import slash_command
from dis_snek.models.scale import Scale

from discordbot import command
from discordbot.command import MtgContext
from magic.models import Card


class Legal(Scale):
    @slash_command('legal')
    @command.slash_card_option()
    async def legal(ctx: MtgContext, card: Card) -> None:
        """Announce whether the specified card is legal or not."""
        await ctx.single_card_text(card, lambda c: '')

    legal.autocomplete('card')(command.autocomplete_card)

def setup(bot: Snake) -> None:
    Legal(bot)
