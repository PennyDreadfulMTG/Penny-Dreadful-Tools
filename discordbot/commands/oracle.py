from interactions import Client
from interactions.models import Extension, slash_command

from discordbot import command
from discordbot.command import MtgContext, autocomplete_card, slash_card_option
from magic.models import Card


class Oracle(Extension):
    @slash_command('oracle')
    @slash_card_option()
    async def oracle(self, ctx: MtgContext, card: Card) -> None:
        """Oracle text of a card."""
        await ctx.single_card_text(card, oracle_text)

    oracle.autocomplete('card')(autocomplete_card)  # type: ignore

    m_o = command.alias_message_command_to_slash_command(oracle, name='o')

def oracle_text(c: Card) -> str:
    return c.oracle_text

def setup(bot: Client) -> None:
    Oracle(bot)
