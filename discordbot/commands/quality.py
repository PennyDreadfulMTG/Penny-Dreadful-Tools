from interactions import Extension, slash_command, Client, OptionType, slash_option

from discordbot.command import MtgContext


class Quality(Extension):
    @slash_command()
    @slash_option('product', 'Product (if not MTGO)', OptionType.STRING)
    async def quality(self, ctx: MtgContext, product: str | None = None) -> None:
        """A reminder about everyone's favorite way to play digital Magic"""
        if not product:
            product = 'Magic Online'
        await ctx.send(f'**{product}** is a Quality™ Program.')

def setup(bot: Client) -> None:
    Quality(bot)
