from dis_snek import Snake
from dis_snek.annotations.argument_annotations import CMD_BODY
from dis_snek.models.application_commands import slash_command
from dis_snek.models.command import message_command
from dis_snek.models.scale import Scale

from discordbot.command import MtgContext, MtgMessageContext, autocomplete_card, slash_card_option
from magic import card_price
from magic.models import Card


class Price(Scale):
    @slash_command('price')
    @slash_card_option()
    async def price(self, ctx: MtgContext, card: Card) -> None:
        """Price information for a card."""
        await ctx.single_card_text(card, card_price.card_price_string)

    price.autocomplete('card')(autocomplete_card)

    @message_command('price')
    async def m_price(self, ctx: MtgMessageContext, cardname: CMD_BODY) -> None:
        ctx.kwargs['card'] = cardname
        await self.price.call_callback(self.price.callback, ctx)

    m_p = message_command('p')(m_price.callback)


def setup(bot: Snake) -> None:
    Price(bot)
