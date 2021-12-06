from dis_snek import Snake
from dis_snek.models.application_commands import slash_command
from dis_snek.models.command import message_command
from dis_snek.models.scale import Scale
from discordbot import command

from discordbot.command import MtgContext, autocomplete_card, slash_card_option
from magic import card_price
from magic.models import Card


class Price(Scale):
    @slash_command('price')
    @slash_card_option()
    async def price(self, ctx: MtgContext, card: Card) -> None:
        """Price information for a card."""
        await ctx.single_card_text(card, card_price.card_price_string)

    price.autocomplete('card')(autocomplete_card)

    m_price = command.alias_card_command_to_message_command(price)
    m_pr = message_command('pr')(m_price.callback)
    m_p = message_command('p')(m_price.callback)


def setup(bot: Snake) -> None:
    Price(bot)
