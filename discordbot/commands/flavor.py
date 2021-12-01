import re
from dis_snek.client import Snake

from dis_snek.models.application_commands import slash_command
from dis_snek.models.command import message_command
from discordbot import command

from discordbot.command import MtgContext, slash_card_option
from magic import image_fetcher, oracle
from magic.models import Card

from dis_snek.models.scale import Scale

class Flavour(Scale):
    @slash_command('flavor')
    @slash_card_option()
    async def flavor(ctx: MtgContext, *, card: Card) -> None:
        """Flavor text of a card"""
        await ctx.single_card_text(card, flavor_text)

    flavor.autocomplete('card')(command.autocomplete_card)

def flavor_text(c: Card) -> str:
    for printing in oracle.get_printings(c):
        if c.preferred_printing is not None and c.preferred_printing != printing.set_code:
            continue
        if printing.flavor is not None:
            return '\n' + printing.flavor + '\n-**' + oracle.get_set(printing.set_id).name + '**'
    if c.preferred_printing is not None:
        return f'No flavor text for {c.preferred_printing}'
    return 'No flavor text available'

def setup(bot: Snake) -> None:
    Flavour(bot)
