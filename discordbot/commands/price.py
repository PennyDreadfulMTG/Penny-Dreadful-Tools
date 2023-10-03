from interactions import Client
from interactions.ext.prefixed_commands import prefixed_command
from interactions.models import Extension, slash_command

from discordbot import command
from discordbot.command import MtgContext, autocomplete_card, slash_card_option
from magic import card_price
from magic.models import Card


class Price(Extension):
    @slash_command('price')
    @slash_card_option()
    async def price(self, ctx: MtgContext, card: Card) -> None:
        """Price information for a card."""
        await ctx.single_card_text(card, card_price.card_price_string)

    price.autocomplete('card')(autocomplete_card)  # type: ignore

    m_price = command.migrate_to_slash_command(price)
    m_pr = prefixed_command('pr')(m_price.callback)
    m_p = prefixed_command('p')(m_price.callback)


def setup(bot: Client) -> None:
    Price(bot)
