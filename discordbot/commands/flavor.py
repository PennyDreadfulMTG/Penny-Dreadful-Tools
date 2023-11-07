from interactions.client import Client
from interactions.models import Extension, slash_command

from discordbot import command
from discordbot.command import MtgInteractionContext, slash_card_option
from magic import oracle
from magic.models import Card


class Flavour(Extension):
    @slash_command('flavor')
    @slash_card_option()
    async def flavor(self, ctx: MtgInteractionContext, card: Card) -> None:
        """Flavor text of a card"""
        await ctx.single_card_text(card, flavor_text)

    m_flavor = command.alias_message_command_to_slash_command(flavor)

def flavor_text(c: Card) -> str:
    for printing in oracle.get_printings(c):
        if c.preferred_printing is not None and c.preferred_printing.lower() != printing.set_code.lower() and c.preferred_printing.lower() != printing.set_name.lower():
            continue
        if printing.flavor is not None:
            return '\n' + printing.flavor + '\n-**' + oracle.get_set(printing.set_id).name + '**'
    if c.preferred_printing is not None:
        return f'No flavor text for {c.preferred_printing}'
    return 'No flavor text available'

def setup(bot: Client) -> None:
    Flavour(bot)
